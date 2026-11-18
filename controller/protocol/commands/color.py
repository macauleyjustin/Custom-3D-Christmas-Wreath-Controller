"""Verified color command builders: E0 01 00 C1 and E1 22 compact color."""

from __future__ import annotations

from typing import Sequence

from controller.exceptions import ValidationError
from controller.protocol.constants import (
    CMD_E0_GLOBAL_FOOTER,
    CMD_E0_GLOBAL_PREFIX,
    CMD_E1_COMPACT_COLOR,
    COMPACT_COLOR_GROUP_COUNT,
)


def _validate_hsvw(hue_byte: int, sat: int, val: int, white_temp: int, white_val: int) -> None:
    if not 0 <= hue_byte <= 180:
        raise ValidationError(f"hue_byte must be in 0..180, got {hue_byte}")
    if not 0 <= sat <= 100:
        raise ValidationError(f"saturation must be in 0..100, got {sat}")
    if not 0 <= val <= 100:
        raise ValidationError(f"value must be in 0..100, got {val}")
    if not 0 <= white_temp <= 100:
        raise ValidationError(f"white_temp must be in 0..100, got {white_temp}")
    if not 0 <= white_val <= 100:
        raise ValidationError(f"white_val must be in 0..100, got {white_val}")


def build_e0_global_color(
    hue_byte: int,
    sat: int = 100,
    val: int = 100,
    white_temp: int = 0,
    white_val: int = 0,
) -> bytes:
    """Build the 14-byte legacy global HSV+W command (``E0 01 00 C1``)."""
    _validate_hsvw(hue_byte, sat, val, white_temp, white_val)
    return (
        CMD_E0_GLOBAL_PREFIX
        + bytes((hue_byte, sat, val, white_temp, white_val))
        + CMD_E0_GLOBAL_FOOTER
    )


def build_compact_color_record(
    hue_byte: int,
    sat: int = 100,
    val: int = 100,
    white_val: int = 0,
) -> bytes:
    """Build one 5-byte compact color record ``[H, S, V, 0x00, W]``."""
    _validate_hsvw(hue_byte, sat, val, 0, white_val)
    return bytes((hue_byte, sat, val, 0x00, white_val))


def build_e1_compact_color(
    groups: Sequence[tuple[int, int, int, int]],
) -> bytes:
    """Build the 107-byte ``E1 22`` 20-group compact color command.

    Each group tuple is ``(hue_byte: 0..180, sat: 0..100, val: 0..100, white: 0..100)``.
    If fewer than 20 groups are passed, raises ValidationError (caller should
    use ``build_e1_compact_solid`` for uniform fill).
    """
    if len(groups) != COMPACT_COLOR_GROUP_COUNT:
        raise ValidationError(
            f"E1 22 requires exactly {COMPACT_COLOR_GROUP_COUNT} groups, got {len(groups)}"
        )
    buf = bytearray((CMD_E1_COMPACT_COLOR, 0x00, 0x00, 0x00, 0x00, COMPACT_COLOR_GROUP_COUNT))
    # Header bytes: E1 22 00 00 00 00 14 (7 bytes total)
    buf = bytearray((0xE1, CMD_E1_COMPACT_COLOR, 0x00, 0x00, 0x00, 0x00, COMPACT_COLOR_GROUP_COUNT))
    for h, s, v, w in groups:
        buf.extend(build_compact_color_record(h, s, v, w))
    return bytes(buf)


def build_e1_compact_solid(
    hue_byte: int,
    sat: int = 100,
    val: int = 100,
    white_val: int = 0,
) -> bytes:
    """Build an ``E1 22`` command setting all 20 groups to one HSV+W color."""
    rec = build_compact_color_record(hue_byte, sat, val, white_val)
    header = bytes((0xE1, CMD_E1_COMPACT_COLOR, 0x00, 0x00, 0x00, 0x00, COMPACT_COLOR_GROUP_COUNT))
    return header + rec * COMPACT_COLOR_GROUP_COUNT
