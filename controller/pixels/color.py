"""Color space conversion and RGB/HSV helpers for Bouffalo 0x6B controllers."""

from __future__ import annotations

import colorsys

from controller.exceptions import ValidationError

RGB = tuple[int, int, int]

NAMED_COLORS: dict[str, RGB] = {
    "RED": (255, 0, 0),
    "ORANGE": (255, 85, 0),
    "YELLOW": (255, 220, 0),
    "GREEN": (0, 255, 0),
    "AQUA": (0, 255, 255),
    "CYAN": (0, 255, 255),
    "BLUE": (0, 0, 255),
    "PURPLE": (180, 0, 255),
    "PINK": (255, 0, 140),
    "WHITE": (255, 255, 255),
    "WARM_WHITE": (255, 210, 140),
    "OFF": (0, 0, 0),
}


def validate_rgb(r: int, g: int, b: int) -> RGB:
    """Validate and return an ``(r, g, b)`` integer tuple in ``0..255``."""
    for name, val in (("r", r), ("g", g), ("b", b)):
        if isinstance(val, bool) or not isinstance(val, int) or not 0 <= val <= 255:
            raise ValidationError(f"RGB component {name} must be int in 0..255, got {val!r}")
    return (r, g, b)


def scale_rgb(rgb: RGB, brightness: float) -> RGB:
    """Scale an RGB tuple by ``brightness`` in ``0.0..1.0``."""
    if not 0.0 <= brightness <= 1.0:
        raise ValidationError(f"brightness must be in 0.0..1.0, got {brightness}")
    r, g, b = rgb
    return (
        max(0, min(255, round(r * brightness))),
        max(0, min(255, round(g * brightness))),
        max(0, min(255, round(b * brightness))),
    )


def rgb_to_hsv_bytes(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Convert RGB ``(0..255)`` to controller HSV bytes ``(hue 0..180, sat 0..100, val 0..100)``."""
    validate_rgb(r, g, b)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue_byte = round(h * 180) % 180
    sat_byte = round(s * 100)
    val_byte = round(v * 100)
    return (hue_byte, sat_byte, val_byte)


def hsv_bytes_to_rgb(hue_byte: int, sat: int, val: int) -> RGB:
    """Convert controller HSV bytes ``(0..180, 0..100, 0..100)`` to RGB ``(0..255)``."""
    h = (hue_byte % 180) / 180.0
    s = max(0.0, min(1.0, sat / 100.0))
    v = max(0.0, min(1.0, val / 100.0))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def interpolate_rgb(c1: RGB, c2: RGB, t: float) -> RGB:
    """Linearly interpolate between two RGB colors with ``t`` clamped to ``0.0..1.0``."""
    t = max(0.0, min(1.0, t))
    return (
        round(c1[0] + (c2[0] - c1[0]) * t),
        round(c1[1] + (c2[1] - c1[1]) * t),
        round(c1[2] + (c2[2] - c1[2]) * t),
    )


def gradient_rgb(stops: list[RGB], count: int) -> list[RGB]:
    """Sample ``count`` evenly spaced RGB pixels across multi-stop ``stops``."""
    if count <= 0:
        raise ValidationError(f"count must be positive, got {count}")
    if not stops:
        raise ValidationError("stops must contain at least one RGB color")
    if len(stops) == 1 or count == 1:
        return [validate_rgb(*stops[0])] * count
    out: list[RGB] = []
    segs = len(stops) - 1
    for i in range(count):
        pos = (i / (count - 1)) * segs
        idx = min(segs - 1, int(pos))
        frac = pos - idx
        out.append(interpolate_rgb(stops[idx], stops[idx + 1], frac))
    return out
