"""Parsers for TCP tunnel frames, BLE JSON payloads, EA 81 state, time, and remote config."""

from __future__ import annotations

import colorsys
import json
from dataclasses import dataclass
from typing import Optional

from controller.exceptions import ProtocolError
from controller.protocol.constants import (
    MODE_COMPACT_COLOR,
    MODE_DOODLE,
    MODE_SCENE,
    POWER_OFF_BYTE,
    POWER_ON_BYTE,
    RESP_EXTENDED_STATE,
    RESP_REMOTE_CONFIG,
    RESP_TIME,
    TUNNEL_MIN_FRAME_LEN,
    TUNNEL_PREAMBLE,
)
from controller.protocol.encoder.tunnel import calculate_sum_checksum


@dataclass(frozen=True)
class TunnelFrame:
    """Decoded outer B0 B1 B2 B3 tunnel packet."""

    version: int
    seq: int
    inner: bytes
    checksum: int
    raw: bytes


@dataclass(frozen=True)
class ExtendedState:
    """Decoded 27-byte 0xEA 0x81 controller state response."""

    model_id: int
    fw_subversion: int
    is_on: bool
    power_byte: int
    mode: int
    pattern: int
    speed: int
    flag10: int
    hue_byte: int          # 0..180
    saturation: int        # 0..100 (or >100 in special presets)
    value: int             # 0..100
    white_temp: int        # 0..100 or 255 if inactive
    white_brightness: int  # 0..100
    byte16: int
    led_count: int
    tail: bytes
    raw: bytes

    @property
    def mode_name(self) -> str:
        """Human-readable mode name."""
        if self.mode == MODE_COMPACT_COLOR:
            return "compact_color"
        if self.mode == MODE_SCENE:
            return "scene"
        if self.mode == MODE_DOODLE:
            return "doodle"
        return f"unknown_0x{self.mode:02x}"

    @property
    def rgb(self) -> tuple[int, int, int]:
        """Approximate RGB (0..255) converted from the reported HSV."""
        h = (self.hue_byte % 180) / 180.0
        s = max(0.0, min(1.0, self.saturation / 100.0))
        v = max(0.0, min(1.0, self.value / 100.0))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (round(r * 255), round(g * 255), round(b * 255))


@dataclass(frozen=True)
class DeviceTime:
    """Decoded 12-byte 0x0F 0x11 RTC time response."""

    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    weekday: int
    raw: bytes

    def isoformat(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}T{self.hour:02d}:{self.minute:02d}:{self.second:02d}"


@dataclass(frozen=True)
class RemoteConfig:
    """Decoded 14-byte 0x2B remote config response."""

    state_flag: int
    remote_mode: int
    raw: bytes


def extract_tunnel_frames(buffer: bytearray) -> list[TunnelFrame]:
    """Extract all complete B0 B1 B2 B3 frames from ``buffer``, mutating ``buffer`` in place.

    Supports both valid tunnel frames and non-tunnel trailing bytes cleanly by
    scanning to the next preamble on framing errors.
    """
    frames: list[TunnelFrame] = []
    while len(buffer) >= TUNNEL_MIN_FRAME_LEN:
        idx = buffer.find(TUNNEL_PREAMBLE)
        if idx == -1:
            # Keep last up to 3 bytes in case a preamble spans TCP recv boundaries.
            if len(buffer) > 3:
                del buffer[:-3]
            break
        if idx > 0:
            del buffer[:idx]
        if len(buffer) < TUNNEL_MIN_FRAME_LEN:
            break

        inner_len = int.from_bytes(buffer[8:10], "big")
        total_len = 10 + inner_len + 1
        if len(buffer) < total_len:
            break

        raw = bytes(buffer[:total_len])
        del buffer[:total_len]

        expected_cs = calculate_sum_checksum(raw[:-1])
        actual_cs = raw[-1]
        if expected_cs != actual_cs:
            raise ProtocolError(
                f"Tunnel checksum mismatch: expected 0x{expected_cs:02x}, got 0x{actual_cs:02x}"
            )

        frames.append(
            TunnelFrame(
                version=raw[6],
                seq=raw[7],
                inner=raw[10:-1],
                checksum=actual_cs,
                raw=raw,
            )
        )
    return frames


def decode_ble_notification(data: bytes) -> Optional[bytes]:
    """Decode a Zengge BLE v0 notification into its inner binary payload."""
    if len(data) < 8:
        return None
    body = data[8:]
    if body and body[0] in (0x7B, 0x5B):  # JSON '{' or '['
        try:
            obj = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ProtocolError(f"Invalid JSON in BLE notification: {exc}") from exc
        if isinstance(obj, dict) and "payload" in obj:
            if obj.get("code", 0) != 0:
                raise ProtocolError(f"BLE controller error response: {obj}")
            return bytes.fromhex(obj["payload"])
    return body


def parse_extended_state(payload: bytes) -> ExtendedState:
    """Parse a 27-byte (or >=20 byte) 0xEA 0x81 extended state response."""
    if len(payload) < 20 or payload[:2] != RESP_EXTENDED_STATE:
        raise ProtocolError(f"Invalid EA 81 extended state payload: {payload.hex()}")
    model_id = int.from_bytes(payload[3:5], "big")
    led_count = int.from_bytes(payload[17:19], "big")
    power_byte = payload[6]
    if power_byte not in (POWER_ON_BYTE, POWER_OFF_BYTE):
        raise ProtocolError(f"Unexpected power byte in EA 81: 0x{power_byte:02x}")
    return ExtendedState(
        model_id=model_id,
        fw_subversion=payload[5],
        is_on=(power_byte == POWER_ON_BYTE),
        power_byte=power_byte,
        mode=payload[7],
        pattern=payload[8],
        speed=payload[9],
        flag10=payload[10],
        hue_byte=payload[11],
        saturation=payload[12],
        value=payload[13],
        white_temp=payload[14],
        white_brightness=payload[15],
        byte16=payload[16],
        led_count=led_count,
        tail=payload[19:],
        raw=payload,
    )


def parse_time_response(payload: bytes) -> DeviceTime:
    """Parse a 12-byte 0x0F 0x11 RTC time response."""
    if len(payload) != 12 or payload[:2] != RESP_TIME:
        raise ProtocolError(f"Invalid 0F 11 time response: {payload.hex()}")
    if calculate_sum_checksum(payload[:-1]) != payload[-1]:
        raise ProtocolError(f"Time response checksum mismatch: {payload.hex()}")
    return DeviceTime(
        year=payload[2] * 100 + payload[3],
        month=payload[4],
        day=payload[5],
        hour=payload[6],
        minute=payload[7],
        second=payload[8],
        weekday=payload[9],
        raw=payload,
    )


def parse_remote_config(payload: bytes) -> RemoteConfig:
    """Parse a 14-byte 0x2B remote config response."""
    if len(payload) != 14 or payload[0] != RESP_REMOTE_CONFIG:
        raise ProtocolError(f"Invalid 2B remote config response: {payload.hex()}")
    if calculate_sum_checksum(payload[:-1]) != payload[-1]:
        raise ProtocolError(f"Remote config checksum mismatch: {payload.hex()}")
    return RemoteConfig(
        state_flag=payload[1],
        remote_mode=payload[3],
        raw=payload,
    )
