"""Physical 3D wreath geometry map (clock angle, radial depth, and 2D coordinates per LED)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

LayerType = Literal["inner", "front", "outer", "back"]

_LAYER_RADIUS: dict[LayerType, float] = {
    "inner": 0.56,
    "front": 0.78,
    "outer": 1.00,
    "back": 0.82,
}


@dataclass(frozen=True)
class WreathLedNode:
    """Physical 3D placement metadata for one addressable LED on the 50-LED wreath."""

    index: int
    clock_hour: float       # 0.0..12.0 (0.0/12.0 = top 12:00, 3.0 = right, 6.0 = bottom, 9.0 = left)
    layer: LayerType        # "inner" | "front" | "outer" | "back"
    mapped_from_user: bool  # True if physically mapped on the wreath, False if interpolated

    @property
    def angle_deg(self) -> float:
        """Clockwise angle in degrees where 0 deg = 12 o'clock top."""
        return (self.clock_hour % 12.0) * 30.0

    @property
    def radius(self) -> float:
        """Normalized radial ring position (~0.56 inner .. 1.00 outer)."""
        return _LAYER_RADIUS[self.layer]

    @property
    def x(self) -> float:
        """Normalized horizontal coordinate (-1.0 left .. +1.0 right)."""
        return self.radius * math.sin(math.radians(self.angle_deg))

    @property
    def y(self) -> float:
        """Normalized vertical coordinate (-1.0 bottom 6:00 .. +1.0 top 12:00)."""
        return self.radius * math.cos(math.radians(self.angle_deg))

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "clock_hour": round(self.clock_hour, 2),
            "angle_deg": round(self.angle_deg, 1),
            "layer": self.layer,
            "radius": self.radius,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "mapped": self.mapped_from_user,
        }


# Directly observed placements reported by physical inspection of LEDs 2 and 7..49:
_OBSERVED_NODES: dict[int, tuple[float, LayerType]] = {
    2:  (12.0, "front"),  # Top of wreath, bottom-front of top branch
    7:  (12.0, "back"),   # Near 2 at top, buried behind branches
    8:  (12.0, "back"),   # Behind 2 at top of wreath
    9:  (12.0, "outer"),  # Very top centered (12:00)
    10: (11.5, "front"),  # Left of 2, middle top-left of center
    11: (12.0, "inner"),  # Right below 2
    12: (1.0,  "back"),   # Top-right ~1:00 in branches
    13: (1.0,  "back"),   # Top-right ~1:00 in branches
    14: (0.6,  "front"),  # Top-middle front ~12-1:00
    15: (0.7,  "inner"),  # Near 14, inner ring ~12-1:00
    16: (2.0,  "back"),   # Behind wreath at 2:00
    17: (2.0,  "back"),   # Behind wreath at 2:00
    18: (2.0,  "back"),   # Behind wreath at 2:00
    19: (2.0,  "inner"),  # Inner ring at 2:00
    20: (3.0,  "back"),   # Behind wreath at 3:00
    21: (3.0,  "back"),   # Behind wreath at 3:00
    22: (2.5,  "front"),  # 2:30 center between inner & outer
    23: (3.0,  "inner"),  # Inner ring at 3:00
    24: (4.0,  "back"),   # Behind wreath ~4:00
    25: (4.0,  "back"),   # Behind wreath ~4:00
    26: (3.5,  "outer"),  # Outer 3-4:00
    27: (3.5,  "inner"),  # Inner 3-4:00
    28: (3.7,  "back"),   # Behind 3-4:00
    29: (3.8,  "back"),   # Behind ~3-4:00
    30: (4.0,  "front"),  # Front 4:00
    31: (4.0,  "back"),   # 4:00 behind
    32: (4.5,  "back"),   # Behind ~4:30
    33: (4.5,  "back"),   # Behind ~4:30
    34: (5.0,  "front"),  # ~5:00
    35: (6.4,  "inner"),  # Between 6-7:00 inner
    36: (6.4,  "back"),   # Same position as 35 but behind
    37: (6.0,  "outer"),  # Outer side 6:00
    38: (6.6,  "inner"),  # Inner ~6-7:00
    39: (7.0,  "inner"),  # Inner slightly in front in branches, 7:00
    40: (7.0,  "back"),   # Inner behind 7:00
    41: (8.0,  "outer"),  # Outer edge left side 8:00
    42: (8.9,  "front"),  # Almost 9:00 dead center
    43: (8.6,  "inner"),  # Inner slightly in branches, front
    44: (10.0, "back"),   # Outer 10:00 rear of wreath
    45: (9.0,  "outer"),  # Left of wreath 9:00
    46: (9.0,  "inner"),  # Inner 9:00
    47: (10.6, "back"),   # Hidden near 49
    48: (10.8, "back"),   # Hidden near 49
    49: (11.2, "inner"),  # Inner of wreath front approaching 12:00
}


def build_wreath_layout(led_count: int = 50) -> list[WreathLedNode]:
    """Return physical placement nodes for ``led_count`` LEDs.

    44 of 50 LEDs (indices 2 and 7..49) use directly observed physical positions.
    Indices 0, 1, and 3..6 are smoothly interpolated between 49 (~11:12) and 7 (~12:00).
    """
    nodes: list[WreathLedNode] = []
    for idx in range(led_count):
        if idx in _OBSERVED_NODES:
            hr, layer = _OBSERVED_NODES[idx]
            nodes.append(WreathLedNode(idx, hr, layer, True))
        elif idx in (0, 1):
            hr = 11.4 + idx * 0.25
            nodes.append(WreathLedNode(idx, hr, "front" if idx == 0 else "back", False))
        elif 3 <= idx <= 6:
            hr = 11.6 + (idx - 3) * 0.1
            nodes.append(WreathLedNode(idx, hr, "front" if idx % 2 == 0 else "back", False))
        else:
            # Fallback for non-50 counts
            hr = (idx / max(1, led_count)) * 12.0
            cycle: tuple[LayerType, ...] = ("front", "back", "inner", "outer")
            nodes.append(WreathLedNode(idx, hr, cycle[idx % 4], False))
    return nodes


DEFAULT_WREATH_LAYOUT: list[WreathLedNode] = build_wreath_layout(50)
