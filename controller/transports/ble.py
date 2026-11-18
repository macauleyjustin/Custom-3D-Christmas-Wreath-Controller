"""BLE GATT 0xFFFF transport (FF01 write / FF02 notify) via CoreBluetooth bridge on macOS."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import threading
import time
from typing import Optional

from controller.diagnostics.capture import PacketCaptureLog
from controller.exceptions import ProtocolError, TransportError, UnsupportedCapabilityError
from controller.protocol.decoder.responses import decode_ble_notification
from controller.protocol.encoder.tunnel import wrap_ble_v0
from controller.transports.base import BaseTransport, TransportStats


_MAC_BLE_BRIDGE_SWIFT = r"""
import CoreBluetooth
import Foundation

setbuf(stdout, nil)

class Bridge: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var mgr: CBCentralManager!
    var target: CBPeripheral?
    var ff01: CBCharacteristic?
    var ff02: CBCharacteristic?
    let targetName: String
    var readySent = false

    init(targetName: String) {
        self.targetName = targetName
        super.init()
        self.mgr = CBCentralManager(delegate: self, queue: DispatchQueue(label: "ble.cb"))
    }

    func emit(_ dict: [String: Any]) {
        if let d = try? JSONSerialization.data(withJSONObject: dict, options: []),
           let s = String(data: d, encoding: .utf8) {
            print(s)
            fflush(stdout)
        }
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            central.scanForPeripherals(withServices: nil, options: nil)
        } else if central.state == .unauthorized || central.state == .unsupported || central.state == .poweredOff {
            emit(["event": "error", "message": "Bluetooth unavailable (state=\(central.state.rawValue))"])
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        let name = peripheral.name ?? (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? ""
        let id = peripheral.identifier.uuidString
        if (name.caseInsensitiveCompare(targetName) == .orderedSame || id.caseInsensitiveCompare(targetName) == .orderedSame), target == nil {
            target = peripheral
            peripheral.delegate = self
            central.stopScan()
            central.connect(peripheral, options: nil)
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([CBUUID(string: "FFFF")])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        emit(["event": "error", "message": error?.localizedDescription ?? "didFailToConnect"])
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        emit(["event": "disconnected", "message": error?.localizedDescription ?? "closed"])
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        for svc in peripheral.services ?? [] {
            peripheral.discoverCharacteristics(nil, for: svc)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for ch in service.characteristics ?? [] {
            if ch.uuid.uuidString == "FF01" { ff01 = ch }
            if ch.uuid.uuidString == "FF02" {
                ff02 = ch
                peripheral.setNotifyValue(true, for: ch)
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if characteristic.uuid.uuidString == "FF02", characteristic.isNotifying, !readySent, ff01 != nil {
            readySent = true
            emit([
                "event": "ready",
                "mtu_with_response": peripheral.maximumWriteValueLength(for: .withResponse),
                "mtu_without_response": peripheral.maximumWriteValueLength(for: .withoutResponse)
            ])
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let v = characteristic.value {
            emit(["event": "notify", "hex": v.map { String(format: "%02x", $0) }.joined()])
        }
    }

    func writeHex(_ hexStr: String, withResponse: Bool) {
        guard let p = target, let ch = ff01 else {
            emit(["event": "error", "message": "not connected"])
            return
        }
        var bytes: [UInt8] = []
        var idx = hexStr.startIndex
        while idx < hexStr.endIndex {
            let next = hexStr.index(idx, offsetBy: 2, limitedBy: hexStr.endIndex) ?? hexStr.endIndex
            if let b = UInt8(hexStr[idx..<next], radix: 16) { bytes.append(b) }
            idx = next
        }
        let data = Data(bytes)
        p.writeValue(data, for: ch, type: withResponse ? .withResponse : .withoutResponse)
    }

    func closeBridge() {
        if let p = target { mgr.cancelPeripheralConnection(p) }
    }
}

let targetName = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "IOTWFC00"
let bridge = Bridge(targetName: targetName)

DispatchQueue.global().async {
    while let line = readLine() {
        guard let d = line.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let cmd = obj["cmd"] as? String else { continue }
        if cmd == "write" {
            let hex = (obj["hex"] as? String) ?? ""
            let resp = (obj["with_response"] as? Bool) ?? false
            bridge.writeHex(hex, withResponse: resp)
        } else if cmd == "quit" {
            bridge.closeBridge()
            exit(0)
        }
    }
    bridge.closeBridge()
    exit(0)
}

RunLoop.main.run()
"""


class BLETransport(BaseTransport):
    """BLE transport over GATT ``0xFFFF`` (``FF01`` write / ``FF02`` notify)."""

    def __init__(
        self,
        device_name_or_id: str = "IOTWFC00",
        *,
        connect_timeout: float = 8.0,
        io_timeout: float = 3.0,
        capture: Optional[PacketCaptureLog] = None,
    ) -> None:
        super().__init__(capture=capture)
        self.device_name_or_id = device_name_or_id
        self.connect_timeout = connect_timeout
        self.io_timeout = io_timeout
        self._lock = threading.RLock()
        self._proc: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._ready_event = threading.Event()
        self._notify_cond = threading.Condition()
        self._notifications: list[bytes] = []
        self._bridge_error: str | None = None
        self._mtu_with_resp = 512
        self._mtu_no_resp = 244
        self._seq = 0
        self._tx_packets = 0
        self._rx_packets = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._reconnects = 0
        self._errors = 0
        self._last_latency_ms: float | None = None
        self._latency_samples = 0
        self._latency_sum_ms = 0.0
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        return "ble"

    @property
    def endpoint(self) -> str:
        return f"ble://{self.device_name_or_id}"

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None and self._ready_event.is_set()

    def _reader_loop(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            text = line.strip()
            if not text:
                continue
            try:
                evt = json.loads(text)
            except json.JSONDecodeError:
                continue
            kind = evt.get("event")
            if kind == "ready":
                self._mtu_with_resp = int(evt.get("mtu_with_response", 512))
                self._mtu_no_resp = int(evt.get("mtu_without_response", 244))
                self._ready_event.set()
            elif kind == "notify":
                raw = bytes.fromhex(evt.get("hex", ""))
                with self._notify_cond:
                    self._notifications.append(raw)
                    self._notify_cond.notify_all()
            elif kind in ("error", "disconnected"):
                self._bridge_error = str(evt.get("message", kind))
                with self._notify_cond:
                    self._notify_cond.notify_all()

    def connect(self) -> None:
        if platform.system() != "Darwin" or not shutil.which("swift"):
            raise UnsupportedCapabilityError(
                "BLETransport currently requires macOS CoreBluetooth with Swift CLI available"
            )
        with self._lock:
            self.disconnect()
            self._ready_event.clear()
            self._bridge_error = None
            self._notifications.clear()

            proc = subprocess.Popen(
                ["swift", "-", self.device_name_or_id],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert proc.stdin is not None
            proc.stdin.write(_MAC_BLE_BRIDGE_SWIFT + "\n")
            # Wait: swift - reads entire stdin until EOF before compiling, so pass script via temp file!
            proc.kill()
            proc.wait()
            raise RuntimeError("unreachable")

    def _ensure_script_path(self) -> str:
        import os
        import tempfile

        path = os.path.join(tempfile.gettempdir(), "hl_ble_bridge.swift")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_MAC_BLE_BRIDGE_SWIFT)
        return path

    def _start_bridge_locked(self) -> None:
        script_path = self._ensure_script_path()
        t0 = time.monotonic()
        proc = subprocess.Popen(
            ["swift", script_path, self.device_name_or_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._proc = proc
        self._reader_thread = threading.Thread(
            target=self._reader_loop, args=(proc,), daemon=True
        )
        self._reader_thread.start()
        if not self._ready_event.wait(timeout=self.connect_timeout):
            err = self._bridge_error or "BLE connection timed out"
            self.disconnect()
            self._errors += 1
            self._last_error = err
            raise TransportError(f"Failed to connect BLE {self.device_name_or_id}: {err}")
        ms = (time.monotonic() - t0) * 1000.0
        self._last_latency_ms = round(ms, 2)
        self._latency_samples += 1
        self._latency_sum_ms += ms

    def disconnect(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
            self._ready_event.clear()
            if proc is not None:
                try:
                    if proc.stdin:
                        proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                        proc.stdin.flush()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    def send_command(
        self,
        inner_payload: bytes,
        *,
        expect_response: bool = False,
        expected_prefix: bytes | None = None,
        idempotent: bool = True,
        timeout: float | None = None,
    ) -> bytes | None:
        eff_timeout = self.io_timeout if timeout is None else timeout
        with self._lock:
            if not self.is_connected:
                self._ready_event.clear()
                self._bridge_error = None
                self._notifications.clear()
                self._start_bridge_locked()
            assert self._proc is not None and self._proc.stdin is not None

            seq = self._seq
            self._seq = (self._seq + 1) & 0xFF
            wire = wrap_ble_v0(inner_payload, seq=seq, expect_response=expect_response)
            if len(wire) > self._mtu_with_resp:
                raise UnsupportedCapabilityError(
                    f"BLE payload ({len(wire)}B) exceeds GATT MTU ({self._mtu_with_resp}B) on {self.endpoint}; "
                    "use Wi-Fi TCP 5577 for full-frame 50-pixel streaming or implement multi-segment fragmentation."
                )
            with_resp = len(wire) > self._mtu_no_resp
            with self._notify_cond:
                self._notifications.clear()

            t0 = time.monotonic()
            self._proc.stdin.write(
                json.dumps({"cmd": "write", "hex": wire.hex(), "with_response": with_resp}) + "\n"
            )
            self._proc.stdin.flush()
            self._tx_packets += 1
            self._tx_bytes += len(wire)
            self.capture.record(
                direction="TX",
                transport=self.name,
                endpoint=self.endpoint,
                seq=seq,
                wire_bytes=wire,
                inner_bytes=inner_payload,
            )

            if not expect_response:
                # Pace fire-and-forget GATT writes so the BL602 BLE task processes before next query
                time.sleep(0.18)
                return None

            deadline = time.monotonic() + eff_timeout
            while True:
                with self._notify_cond:
                    while self._notifications:
                        raw = self._notifications.pop(0)
                        self._rx_packets += 1
                        self._rx_bytes += len(raw)
                        try:
                            decoded = decode_ble_notification(raw)
                        except ProtocolError as exc:
                            self._errors += 1
                            self._last_error = str(exc)
                            raise
                        if decoded is None:
                            continue
                        ms = round((time.monotonic() - t0) * 1000.0, 2)
                        self.capture.record(
                            direction="RX",
                            transport=self.name,
                            endpoint=self.endpoint,
                            seq=seq,
                            wire_bytes=raw,
                            inner_bytes=decoded,
                            latency_ms=ms,
                        )
                        if expected_prefix is None or decoded.startswith(expected_prefix):
                            self._last_latency_ms = ms
                            self._latency_samples += 1
                            self._latency_sum_ms += ms
                            return decoded
                    rem = deadline - time.monotonic()
                    if rem <= 0:
                        self._errors += 1
                        raise TransportError(f"BLE response timeout after {eff_timeout:.2f}s")
                    self._notify_cond.wait(timeout=rem)

    def stats(self) -> TransportStats:
        with self._lock:
            avg = (
                round(self._latency_sum_ms / self._latency_samples, 2)
                if self._latency_samples
                else None
            )
            return TransportStats(
                transport_type=self.name,
                endpoint=self.endpoint,
                connected=self.is_connected,
                tx_packets=self._tx_packets,
                rx_packets=self._rx_packets,
                tx_bytes=self._tx_bytes,
                rx_bytes=self._rx_bytes,
                reconnects=self._reconnects,
                errors=self._errors,
                last_latency_ms=self._last_latency_ms,
                avg_latency_ms=avg,
                last_error=self._last_error,
            )


# Replace broken connect() method cleanly (fix inline stub)
def _ble_connect(self: BLETransport) -> None:
    if platform.system() != "Darwin" or not shutil.which("swift"):
        raise UnsupportedCapabilityError(
            "BLETransport currently requires macOS CoreBluetooth with Swift CLI available"
        )
    with self._lock:
        self.disconnect()
        self._ready_event.clear()
        self._bridge_error = None
        self._notifications.clear()
        self._start_bridge_locked()


BLETransport.connect = _ble_connect  # type: ignore[method-assign]
