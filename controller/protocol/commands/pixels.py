"""Verified pixel frame commands: E1 23 Doodle frame and E1 26 frame options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from controller.exceptions import ValidationError
from controller.protocol.constants import (
    CMD_E1_DOODLE_FRAME,
    CMD_E1_FRAME_OPTIONS,
    FRAME_ANIM_OPTIONS,
    PIXEL_ANIM_STATIC,
    VALID_PIXEL_ANIMS,
)


@dataclass(frozen=True)
class DoodlePixel:
    """Single 7-byte pixel entry for an ``E1 23`` Doodle frame."""

    hue_byte: int
    sat: int = 100
    val: int = 100
    anim: int = PIXEL_ANIM_STATIC
    pixel_speed: int = 100

    def encode(self) -> bytes:
        if self.anim not in VALID_PIXEL_ANIMS:
            raise ValidationError(
                f"pixel anim must be one of {sorted(VALID_PIXEL_ANIMS)}, got 0x{self.anim:02x}"
            )
        if not 0 <= self.hue_byte <= 180:
            raise ValidationError(f"hue_byte must be in 0..180, got {self.hue_byte}")
        if not 0 <= self.sat <= 100:
            raise ValidationError(f"sat must be in 0..100, got {self.sat}")
        if not 0 <= self.val <= 100:
            raise ValidationError(f"val must be in 0..100, got {self.val}")
        if not 0 <= self.pixel_speed <= 100:
            raise ValidationError(f"pixel_speed must be in 0..100, got {self.pixel_speed}")
        return bytes((self.anim, self.hue_byte, self.sat, self.val, 0x00, 0x00, self.pixel_speed))


def build_e1_doodle_frame(
    pixels: Sequence[DoodlePixel],
    *,
    speed: int = 100,
    header_flags: tuple[int, int, int, int] = (0x00, 0x00, 0x00, 0x50),
) -> bytes:
    """Build an ``E1 23`` per-pixel Doodle frame payload.

    Verified layout:
        ``E1 23 [f0] [f1] [f2] [f3] [speed] [cnt_hi] [cnt_lo] [N x 7B DoodlePixel]``
    """
    if not 1 <= len(pixels) <= 0xFFFF:
        raise ValidationError(f"pixel count must be 1..65535, got {len(pixels)}")
    if not 0 <= speed <= 100:
        raise ValidationError(f"speed must be in 0..100, got {speed}")
    if len(header_flags) != 4 or any(not 0 <= b <= 0xFF for b in header_flags):
        raise ValidationError("header_flags must be 4 byte integers")

    buf = bytearray((0xE1, CMD_E1_DOODLE_FRAME, *header_flags, speed))
    buf.extend(len(pixels).to_bytes(2, "big"))
    for px in pixels:
        buf.extend(px.encode())
    return bytes(buf)


def decode_e1_doodle_frame(payload: bytes) -> tuple[int, list[DoodlePixel]]:
    """Decode an ``E1 23`` inner payload into ``(speed, pixels)``."""
    if len(payload) < 9 or payload[0] != 0xE1 or payload[1] != CMD_E1_DOODLE_FRAME:
        raise ValidationError("Not a valid E1 23 Doodle frame")
    speed = payload[6]
    count = int.from_bytes(payload[7:9], "big")
    expected_len = 9 + count * 7
    if len(payload) != expected_len:
        raise ValidationError(
            f"E1 23 length mismatch: header declares {count} pixels ({expected_len}B), got {len(payload)}B"
        )
    pixels: list[DoodlePixel] = []
    for idx in range(count):
        off = 9 + idx * 7
        rec = payload[off : off + 7]
        pixels.append(
            DoodlePixel(
                anim=rec[0],
                hue_byte=rec[1],
                sat=rec[2],
                val=rec[3],
                pixel_speed=rec[6],
            )
        )
    return speed, pixels


def build_e1_frame_options(
    option: int | str,
    speed: int = 100,
    frame_format: int = 0x02,
) -> bytes:
    """Build the 51-byte ``E1 26`` dynamic frame animation options command.

    Empirical testing on 0x6B confirmed ``EA 81`` reflects ``pat = OO + 1``
    and ``spd = speed`` in ``mode = 0x66``.
    """
    if isinstance(option, str):
        key = option.lower().replace(" ", "_").replace("-", "_")
        if key not in FRAME_ANIM_OPTIONS:
            raise ValidationError(f"Unknown E1 26 frame option: {option!r}")
        oo = FRAME_ANIM_OPTIONS[key]
    else:
        oo = option
    if not 0 <= oo <= 0xFF:
        raise ValidationError(f"option byte out of range: {oo}")
    if not 0 <= speed <= 100:
        raise ValidationError(f"speed must be in 0..100, got {speed}")
    if not 0 <= frame_format <= 0xFF:
        raise ValidationError(f"frame_format byte out of range: {frame_format}")
    return bytes((0xE1, CMD_E1_FRAME_OPTIONS, oo, frame_format, 0x50, speed)) + bytes(45)
