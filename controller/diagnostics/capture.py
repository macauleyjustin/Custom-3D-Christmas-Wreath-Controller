"""Thread-safe packet logging and exportable diagnostic captures."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PacketLogEntry:
    """Single logged TX or RX transport frame."""

    timestamp: float
    direction: str          # "TX" or "RX"
    transport: str          # "wifi", "ble", "simulator"
    endpoint: str
    seq: int | None
    wire_hex: str
    inner_hex: str
    opcode: str
    summary: str
    latency_ms: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def describe_inner_payload(inner: bytes) -> tuple[str, str]:
    """Return ``(opcode_hex, human_summary)`` for an inner command or response."""
    if not inner:
        return ("", "empty")
    if len(inner) >= 2 and inner[:2] == b"\xea\x81":
        pwr = "ON" if len(inner) > 6 and inner[6] == 0x23 else "OFF"
        mode = f"0x{inner[7]:02x}" if len(inner) > 7 else "?"
        leds = int.from_bytes(inner[17:19], "big") if len(inner) >= 19 else 0
        return ("EA81", f"ExtendedState power={pwr} mode={mode} leds={leds}")
    if len(inner) >= 2 and inner[:2] == b"\x0f\x11":
        return ("0F11", f"RTCTime len={len(inner)}")
    if inner[0] == 0x2B:
        return ("2B", f"RemoteConfig len={len(inner)}")
    if inner[:3] == b"\x81\x8a\x8b":
        return ("818A8B", "StateQuery")
    if inner[:3] == b"\x71\x23\x0f":
        return ("71230F", "PowerOn")
    if inner[:3] == b"\x71\x24\x0f":
        return ("71240F", "PowerOff")
    if inner[:4] == b"\x11\x1a\x1b\x0f":
        return ("111A1B0F", "TimeQuery")
    if inner[:3] == b"\x2b\x2c\x2d":
        return ("2B2C2D", "RemoteConfigQuery")
    if inner[:4] == b"\xe0\x01\x00\xc1" and len(inner) >= 9:
        return ("E00100C1", f"GlobalHSVW H={inner[4]} S={inner[5]} V={inner[6]} WT={inner[7]} WB={inner[8]}")
    if inner[:2] == b"\xe1\x21" and len(inner) >= 16:
        return ("E121", f"CustomScene mm=0x{inner[4]:02x} spd={inner[8]} colors={inner[15]}")
    if inner[:2] == b"\xe1\x22" and len(inner) >= 12:
        return ("E122", f"CompactColor groups={inner[6]} g0=({inner[7]},{inner[8]},{inner[9]},w={inner[11]})")
    if inner[:2] == b"\xe1\x23" and len(inner) >= 9:
        cnt = int.from_bytes(inner[7:9], "big")
        return ("E123", f"DoodleFrame pixels={cnt} spd={inner[6]}")
    if inner[:2] == b"\xe1\x26" and len(inner) >= 6:
        return ("E126", f"FrameOptions oo=0x{inner[2]:02x} fmt=0x{inner[3]:02x} spd={inner[5]}")
    return (inner[:2].hex().upper(), f"Raw len={len(inner)}")


class PacketCaptureLog:
    """Thread-safe bounded ring buffer for protocol inspection and JSON export."""

    def __init__(self, maxlen: int = 1000) -> None:
        self._entries: deque[PacketLogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counter = 0

    def record(
        self,
        *,
        direction: str,
        transport: str,
        endpoint: str,
        seq: int | None,
        wire_bytes: bytes,
        inner_bytes: bytes,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> PacketLogEntry:
        opcode, summary = describe_inner_payload(inner_bytes)
        entry = PacketLogEntry(
            timestamp=time.time(),
            direction=direction,
            transport=transport,
            endpoint=endpoint,
            seq=seq,
            wire_hex=wire_bytes.hex(),
            inner_hex=inner_bytes.hex(),
            opcode=opcode,
            summary=summary,
            latency_ms=latency_ms,
            error=error,
        )
        with self._lock:
            self._entries.append(entry)
            self._counter += 1
        return entry

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._entries)[-max(1, limit) :]
        return [item.to_dict() for item in reversed(items)]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def export_json(self, metadata: dict[str, Any] | None = None) -> str:
        with self._lock:
            entries = [e.to_dict() for e in self._entries]
            total = self._counter
        payload = {
            "exported_at": time.time(),
            "total_recorded": total,
            "buffered_count": len(entries),
            "metadata": metadata or {},
            "packets": entries,
        }
        return json.dumps(payload, indent=2)
