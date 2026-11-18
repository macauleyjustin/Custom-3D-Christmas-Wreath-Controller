"""Verified controller-native scene command builders (E1 21)."""

from __future__ import annotations

from typing import Sequence

from controller.exceptions import ValidationError
from controller.protocol.commands.color import build_compact_color_record
from controller.protocol.constants import CMD_E1_SCENE, SCENE_PROGRAMS


def build_e1_custom_scene(
    program: int | str,
    colors: Sequence[tuple[int, int, int, int]],
    *,
    speed: int = 50,
    option_one: int = 0x00,
    option_two: int = 0x01,
    mode_param: int = 0x64,
    write_context: int = 0x00,
) -> bytes:
    """Build an ``E1 21`` controller-native custom scene command.

    Layout:
        ``E1 21 [WW] [64] [MM] [OO] [FF] [PP] [SS] 00 00 00 00 00 00 [NN] [NN x 5B color]``
    """
    if isinstance(program, str):
        key = program.lower().replace(" ", "_").replace("-", "_")
        if key not in SCENE_PROGRAMS:
            raise ValidationError(f"Unknown E1 21 scene program: {program!r}")
        mm = SCENE_PROGRAMS[key]
    else:
        mm = program

    if not 1 <= len(colors) <= 0xFF:
        raise ValidationError(f"E1 21 requires 1..255 colors, got {len(colors)}")
    if not 0 <= speed <= 100:
        raise ValidationError(f"speed must be in 0..100, got {speed}")
    for name, val in (
        ("program", mm),
        ("option_one", option_one),
        ("option_two", option_two),
        ("mode_param", mode_param),
        ("write_context", write_context),
    ):
        if not 0 <= val <= 0xFF:
            raise ValidationError(f"{name} must be 0..255, got {val}")

    header = bytearray(
        (
            0xE1,
            CMD_E1_SCENE,
            write_context,
            0x64,
            mm,
            option_one,
            option_two,
            mode_param,
            speed,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            len(colors),
        )
    )
    for h, s, v, w in colors:
        header.extend(build_compact_color_record(h, s, v, w))
    return bytes(header)
