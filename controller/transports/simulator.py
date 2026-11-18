"""Virtual 0x6B (AK001-ZJ21413) controller simulator & SimulatorTransport."""

from __future__ import annotations

import datetime
import threading
import time
from typing import Optional

from controller.diagnostics.capture import PacketCaptureLog
from controller.exceptions import ProtocolError, TransportError
from controller.protocol.commands.pixels import DoodlePixel, decode_e1_doodle_frame
from controller.protocol.constants import (
    DEFAULT_PIXEL_COUNT,
    MODE_COMPACT_COLOR,
    MODE_DOODLE,
    MODE_SCENE,
    MODEL_ID_WREATH_6B,
    POWER_OFF_BYTE,
    POWER_ON_BYTE,
)
from controller.protocol.decoder.responses import extract_tunnel_frames
from controller.protocol.encoder.tunnel import calculate_sum_checksum, wrap_tcp_tunnel
from controller.transports.base import BaseTransport, TransportStats


class SimulatedWreathDevice:
    """In-memory state machine mimicking the BL602 AK001-ZJ21413 (0x6B) firmware."""

    def __init__(self, led_count: int = DEFAULT_PIXEL_COUNT) -> None:
        self.led_count = led_count
        self.model_id = MODEL_ID_WREATH_6B
        self.fw_subversion = 0x09
        self.is_on = True
        self.mode = MODE_SCENE
        self.pattern = 0x66
        self.speed = 50
        self.hue_byte = 180
        self.saturation = 100
        self.value = 100
        self.white_temp = 255
        self.white_brightness = 0
        self.compact_groups: list[tuple[int, int, int, int]] = [(180, 100, 100, 0)] * 20
        self.pixels: list[DoodlePixel] = [DoodlePixel(180, 100, 100)] * led_count
        self.command_log: list[bytes] = []

        # Fault-injection hooks for automated testing
        self.simulated_latency_s: float = 0.0
        self.fail_next_send: bool = False
        self.timeout_next_query: bool = False
        self.corrupt_next_checksum: bool = False

    def build_ea81_payload(self) -> bytes:
        pwr = POWER_ON_BYTE if self.is_on else POWER_OFF_BYTE
        buf = bytearray(
            [
                0xEA,
                0x81,
                0x01,
                (self.model_id >> 8) & 0xFF,
                self.model_id & 0xFF,
                self.fw_subversion,
                pwr,
                self.mode,
                self.pattern,
                self.speed,
                0xF0,
                self.hue_byte,
                self.saturation,
                self.value,
                self.white_temp,
                self.white_brightness,
                0x0C,
            ]
        )
        buf.extend(self.led_count.to_bytes(2, "big"))
        buf.extend(bytes((0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x00, 0x03)))
        return bytes(buf)

    def build_time_payload(self) -> bytes:
        now = datetime.datetime.now()
        body = bytes(
            (
                0x0F,
                0x11,
                now.year // 100,
                now.year % 100,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.second,
                now.isoweekday(),
                0x00,
            )
        )
        return body + bytes((calculate_sum_checksum(body),))

    def build_remote_payload(self) -> bytes:
        body = bytes((0x2B, 0x03, 0x00, 0x01, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
        return body + bytes((calculate_sum_checksum(body),))

    def process_inner(self, inner: bytes) -> bytes | None:
        self.command_log.append(inner)
        if inner[:3] == b"\x81\x8a\x8b":
            return self.build_ea81_payload()
        if inner[:4] == b"\x11\x1a\x1b\x0f":
            return self.build_time_payload()
        if inner[:3] == b"\x2b\x2c\x2d":
            return self.build_remote_payload()
        if inner[:3] == b"\x71\x23\x0f":
            self.is_on = True
            return None
        if inner[:3] == b"\x71\x24\x0f":
            self.is_on = False
            return None
        if inner[:4] == b"\xe0\x01\x00\xc1" and len(inner) >= 9:
            self.mode = MODE_SCENE
            self.pattern = 0x66
            self.hue_byte = 180 if inner[4] == 0 else inner[4]
            self.saturation = inner[5]
            self.value = inner[6]
            self.white_temp = inner[7] if inner[8] > 0 else 255
            self.white_brightness = inner[8]
            return None
        if inner[:2] == b"\xe1\x22" and len(inner) >= 7 + 20 * 5:
            self.mode = MODE_COMPACT_COLOR
            self.pattern = 0x01
            groups: list[tuple[int, int, int, int]] = []
            for idx in range(20):
                off = 7 + idx * 5
                groups.append((inner[off], inner[off + 1], inner[off + 2], inner[off + 4]))
            self.compact_groups = groups
            h0, s0, v0, w0 = groups[0]
            self.hue_byte = 180 if (h0 == 0 and s0 > 0) else h0
            self.saturation = s0
            self.value = v0
            self.white_temp = 0 if w0 > 0 else 255
            self.white_brightness = w0
            return None
        if inner[:2] == b"\xe1\x23":
            spd, pixels = decode_e1_doodle_frame(inner)
            self.mode = MODE_DOODLE
            self.pattern = 0x01
            self.speed = spd
            for i in range(min(self.led_count, len(pixels))):
                self.pixels[i] = pixels[i]
            return None
        if inner[:2] == b"\xe1\x26" and len(inner) >= 6:
            self.mode = MODE_DOODLE
            self.pattern = (inner[2] + 1) & 0xFF
            self.speed = inner[5]
            return None
        if inner[:2] == b"\xe1\x21" and len(inner) >= 16:
            self.mode = MODE_SCENE
            self.pattern = inner[4]
            self.speed = inner[8]
            if inner[15] > 0 and len(inner) >= 21:
                h0, s0, v0, w0 = inner[16], inner[17], inner[18], inner[20]
                self.hue_byte = 180 if (h0 == 0 and s0 > 0) else h0
                self.saturation = s0
                self.value = v0
                self.white_brightness = w0
            return None
        return None


class SimulatorTransport(BaseTransport):
    """In-process transport backed by :class:`SimulatedWreathDevice`."""

    def __init__(
        self,
        device: Optional[SimulatedWreathDevice] = None,
        *,
        endpoint_name: str = "sim://wreath-50",
        capture: Optional[PacketCaptureLog] = None,
    ) -> None:
        super().__init__(capture=capture)
        self.device = device if device is not None else SimulatedWreathDevice()
        self._endpoint_name = endpoint_name
        self._lock = threading.RLock()
        self._connected = False
        self._seq = 0
        self._tx_packets = 0
        self._rx_packets = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._reconnects = 0
        self._errors = 0
        self._last_latency_ms: float | None = 0.5
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        return "simulator"

    @property
    def endpoint(self) -> str:
        return self._endpoint_name

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def connect(self) -> None:
        with self._lock:
            self._connected = True
            self._last_error = None

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False

    def send_command(
        self,
        inner_payload: bytes,
        *,
        expect_response: bool = False,
        expected_prefix: bytes | None = None,
        idempotent: bool = True,
        timeout: float = 2.0,
    ) -> bytes | None:
        with self._lock:
            if not self._connected:
                self.connect()
            attempts = 2 if idempotent else 1
            for attempt in range(attempts):
                if attempt > 0:
                    self._reconnects += 1
                    self.connect()
                if self.device.fail_next_send:
                    self.device.fail_next_send = False
                    self._errors += 1
                    self._last_error = "Simulated socket drop"
                    self._connected = False
                    if attempt + 1 < attempts:
                        continue
                    raise TransportError("Simulated socket drop")

                seq = self._seq
                self._seq = (self._seq + 1) & 0xFF
                wire = wrap_tcp_tunnel(inner_payload, seq=seq)
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

                if self.device.simulated_latency_s > 0:
                    time.sleep(self.device.simulated_latency_s)

                buf = bytearray(wire)
                frames = extract_tunnel_frames(buf)
                resp_inner = self.device.process_inner(frames[0].inner)

                if not expect_response:
                    return None
                if self.device.timeout_next_query:
                    self.device.timeout_next_query = False
                    self._errors += 1
                    self._last_error = "Simulated query timeout"
                    raise TransportError("Simulated query timeout")
                if resp_inner is None:
                    raise TransportError("Simulator produced no response for expected query")

                resp_wire = wrap_tcp_tunnel(resp_inner, seq=seq)
                if self.device.corrupt_next_checksum:
                    self.device.corrupt_next_checksum = False
                    resp_wire = resp_wire[:-1] + bytes(((resp_wire[-1] ^ 0xFF) & 0xFF,))

                rx_buf = bytearray(resp_wire)
                try:
                    parsed = extract_tunnel_frames(rx_buf)
                except ProtocolError as exc:
                    self._errors += 1
                    self._last_error = str(exc)
                    raise
                self._rx_packets += 1
                self._rx_bytes += len(resp_wire)
                self.capture.record(
                    direction="RX",
                    transport=self.name,
                    endpoint=self.endpoint,
                    seq=seq,
                    wire_bytes=resp_wire,
                    inner_bytes=parsed[0].inner,
                    latency_ms=0.5,
                )
                return parsed[0].inner
            return None

    def stats(self) -> TransportStats:
        with self._lock:
            return TransportStats(
                transport_type=self.name,
                endpoint=self.endpoint,
                connected=self._connected,
                tx_packets=self._tx_packets,
                rx_packets=self._rx_packets,
                tx_bytes=self._tx_bytes,
                rx_bytes=self._rx_bytes,
                reconnects=self._reconnects,
                errors=self._errors,
                last_latency_ms=self._last_latency_ms,
                avg_latency_ms=self._last_latency_ms,
                last_error=self._last_error,
            )
