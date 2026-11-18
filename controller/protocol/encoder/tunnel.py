"""TCP tunnel and BLE v0 transport packet framing."""

from __future__ import annotations

from controller.exceptions import ValidationError
from controller.protocol.constants import (
    BLE_V0_CMD_EXPECT_RESPONSE,
    BLE_V0_CMD_NO_RESPONSE,
    BLE_V0_FRAG_SINGLE,
    TUNNEL_FIXED_PREFIX,
    TUNNEL_PREAMBLE,
    TUNNEL_VERSION_DEFAULT,
)


def calculate_sum_checksum(data: bytes | bytearray) -> int:
    """Compute standard LEDENET modulo-256 checksum over ``data``.

    Note: ``sum(B0 B1 B2 B3) == 710 == 198 (mod 256)``, so summing the
    entire packet from ``0xB0`` through the end of payload is mathematically
    identical to the ``(sum(data_block) + 198) % 256`` formula observed
    in early reverse-engineering scripts.
    """
    return sum(data) & 0xFF


def wrap_tcp_tunnel(
    inner_payload: bytes | bytearray,
    seq: int,
    version: int = TUNNEL_VERSION_DEFAULT,
) -> bytes:
    """Wrap an inner command payload in the ``B0 B1 B2 B3`` TCP tunnel frame."""
    if not isinstance(inner_payload, (bytes, bytearray)) or not inner_payload:
        raise ValidationError("inner_payload must be non-empty bytes")
    if len(inner_payload) > 0xFFFF:
        raise ValidationError(f"inner_payload too large: {len(inner_payload)} bytes")
    if not 0 <= version <= 0xFF:
        raise ValidationError(f"version out of range: {version}")

    length = len(inner_payload)
    frame = bytearray(TUNNEL_PREAMBLE)
    frame.extend(TUNNEL_FIXED_PREFIX)
    frame.append(version & 0xFF)
    frame.append(seq & 0xFF)
    frame.extend(length.to_bytes(2, "big"))
    frame.extend(inner_payload)
    frame.append(calculate_sum_checksum(frame))
    return bytes(frame)


def wrap_ble_v0(
    inner_payload: bytes | bytearray,
    seq: int,
    expect_response: bool = False,
) -> bytes:
    """Wrap an inner command payload in the Zengge BLE v0 transport header."""
    if not isinstance(inner_payload, (bytes, bytearray)) or not inner_payload:
        raise ValidationError("inner_payload must be non-empty bytes")
    length = len(inner_payload)
    if length > 0xFFFF:
        raise ValidationError(f"inner_payload too large for BLE v0: {length}")

    cmd_id = BLE_V0_CMD_EXPECT_RESPONSE if expect_response else BLE_V0_CMD_NO_RESPONSE
    header = bytearray(8)
    header[0] = 0x00
    header[1] = seq & 0xFF
    header[2:4] = BLE_V0_FRAG_SINGLE
    header[4:6] = length.to_bytes(2, "big")
    header[6] = (length + 1) & 0xFF
    header[7] = cmd_id
    return bytes(header) + bytes(inner_payload)


def append_inner_checksum(payload: bytes | bytearray) -> bytes:
    """Return ``payload`` with its modulo-256 sum checksum appended."""
    raw = bytes(payload)
    return raw + bytes((calculate_sum_checksum(raw),))
