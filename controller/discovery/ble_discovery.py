"""BLE discovery and 0x5A01 advertisement parsing for IOTWFC00 devices."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import dataclass

from controller.protocol.constants import BLE_DEVICE_NAME_PREFIX


@dataclass(frozen=True)
class DiscoveredBLEDevice:
    """Discovered BLE peripheral matching Zengge / IOTWFC advertisements."""

    name: str
    identifier: str
    rssi: int
    mac: str = ""
    model_id: int | None = None
    fw_minor: int | None = None
    fw_subversion: int | None = None
    service_data_hex: str = ""


def parse_5a01_service_data(data: bytes) -> dict[str, object]:
    """Decode the 14-byte ``0x5A01`` service data observed on ``IOTWFC00``.

    Verified live sample: ``52 07 b4 e8 42 a7 fc 00 00 6b 1e 09 01 02``
    - ``[2:8]`` = MAC (``B4:E8:42:A7:FC:00``)
    - ``[8:10]`` = Model ID big-endian (``0x006B``)
    - ``[10]`` = Firmware build minor (``0x1E`` = 30)
    - ``[11]`` = Hardware/protocol subversion (``0x09`` = 9)
    """
    if len(data) < 12:
        return {}
    mac = ":".join(f"{b:02X}" for b in data[2:8])
    return {
        "mac": mac,
        "model_id": int.from_bytes(data[8:10], "big"),
        "fw_minor": data[10],
        "fw_subversion": data[11],
        "flags_hex": data[12:].hex(),
    }


_MAC_BLE_SCAN_SWIFT = r"""
import CoreBluetooth
import Foundation

class Scanner: NSObject, CBCentralManagerDelegate {
    var mgr: CBCentralManager!
    var items: [String: [String: Any]] = [:]
    let prefix: String
    init(prefix: String) {
        self.prefix = prefix
        super.init()
        self.mgr = CBCentralManager(delegate: self, queue: nil)
    }
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        }
    }
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = peripheral.name ?? (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? ""
        if name.uppercased().hasPrefix(prefix) || advertisementData[CBAdvertisementDataServiceDataKey] != nil {
            var svcHex = ""
            if let svcData = advertisementData[CBAdvertisementDataServiceDataKey] as? [CBUUID: Data],
               let d = svcData[CBUUID(string: "5A01")] {
                svcHex = d.map { String(format: "%02x", $0) }.joined()
            } else if !name.uppercased().hasPrefix(prefix) {
                return
            }
            let id = peripheral.identifier.uuidString
            items[id] = [
                "name": name,
                "identifier": id,
                "rssi": RSSI.intValue,
                "service_data_hex": svcHex
            ]
        }
    }
}
let prefix = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "IOTWFC"
let timeout = CommandLine.arguments.count > 2 ? (Double(CommandLine.arguments[2]) ?? 2.5) : 2.5
let scanner = Scanner(prefix: prefix)
RunLoop.main.run(until: Date(timeIntervalSinceNow: timeout))
let out = Array(scanner.items.values)
let data = try JSONSerialization.data(withJSONObject: out, options: [])
print(String(data: data, encoding: .utf8) ?? "[]")
"""


def discover_ble_devices(
    timeout: float = 2.5,
    name_prefix: str = BLE_DEVICE_NAME_PREFIX,
) -> list[DiscoveredBLEDevice]:
    """Scan nearby BLE advertisements for ``IOTWFC*`` / ``0x5A01`` controllers."""
    if platform.system() == "Darwin" and shutil.which("swift"):
        try:
            proc = subprocess.run(
                ["swift", "-", name_prefix.upper(), str(timeout)],
                input=_MAC_BLE_SCAN_SWIFT,
                capture_output=True,
                text=True,
                timeout=max(5.0, timeout + 4.0),
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                raw_list = json.loads(proc.stdout.strip().splitlines()[-1])
                devices: list[DiscoveredBLEDevice] = []
                for item in raw_list:
                    svc_hex = str(item.get("service_data_hex", ""))
                    parsed = parse_5a01_service_data(bytes.fromhex(svc_hex)) if svc_hex else {}
                    devices.append(
                        DiscoveredBLEDevice(
                            name=str(item.get("name", "")),
                            identifier=str(item.get("identifier", "")),
                            rssi=int(item.get("rssi", 0)),
                            mac=str(parsed.get("mac", "")),
                            model_id=parsed.get("model_id"),  # type: ignore[arg-type]
                            fw_minor=parsed.get("fw_minor"),  # type: ignore[arg-type]
                            fw_subversion=parsed.get("fw_subversion"),  # type: ignore[arg-type]
                            service_data_hex=svc_hex,
                        )
                    )
                return devices
        except Exception:
            return []
    return []
