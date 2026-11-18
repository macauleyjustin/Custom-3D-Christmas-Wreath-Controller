"""Logical pixel framebuffer with per-pixel color, animation, and master brightness."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Sequence

from controller.exceptions import ValidationError
from controller.pixels.color import RGB, gradient_rgb, scale_rgb, validate_rgb
from controller.protocol.constants import (
    DEFAULT_PIXEL_COUNT,
    PIXEL_ANIM_STATIC,
    VALID_PIXEL_ANIMS,
)


@dataclass(frozen=True)
class PixelSlot:
    """Logical state for one LED in the framebuffer."""

    rgb: RGB = (0, 0, 0)
    anim: int = PIXEL_ANIM_STATIC
    pixel_speed: int = 100


class PixelFrameBuffer:
    """Thread-safe staging framebuffer for ``N`` logical addressable LEDs."""

    def __init__(self, count: int = DEFAULT_PIXEL_COUNT) -> None:
        if count < 1 or count > 0xFFFF:
            raise ValidationError(f"Pixel count must be 1..65535, got {count}")
        self._count = count
        self._brightness = 1.0
        self._lock = threading.RLock()
        self._slots: list[PixelSlot] = [PixelSlot() for _ in range(count)]

    @property
    def count(self) -> int:
        return self._count

    @property
    def brightness(self) -> float:
        with self._lock:
            return self._brightness

    def set_brightness(self, level: float) -> None:
        if isinstance(level, bool) or not isinstance(level, (int, float)) or not 0.0 <= float(level) <= 1.0:
            raise ValidationError(f"brightness must be in 0.0..1.0, got {level!r}")
        with self._lock:
            self._brightness = float(level)

    def _validate_index(self, index: int) -> None:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < self._count:
            raise ValidationError(f"pixel index {index!r} out of bounds for 0..{self._count - 1}")

    def set_pixel(
        self,
        index: int,
        r: int,
        g: int,
        b: int,
        *,
        anim: int = PIXEL_ANIM_STATIC,
        pixel_speed: int = 100,
    ) -> None:
        self._validate_index(index)
        rgb = validate_rgb(r, g, b)
        if anim not in VALID_PIXEL_ANIMS:
            raise ValidationError(f"Invalid pixel anim 0x{anim:02x}")
        if not 0 <= pixel_speed <= 100:
            raise ValidationError(f"pixel_speed must be 0..100, got {pixel_speed}")
        with self._lock:
            self._slots[index] = PixelSlot(rgb=rgb, anim=anim, pixel_speed=pixel_speed)

    def get_pixel(self, index: int) -> PixelSlot:
        self._validate_index(index)
        with self._lock:
            return self._slots[index]

    def fill(
        self,
        r: int,
        g: int,
        b: int,
        *,
        anim: int = PIXEL_ANIM_STATIC,
        pixel_speed: int = 100,
    ) -> None:
        rgb = validate_rgb(r, g, b)
        if anim not in VALID_PIXEL_ANIMS:
            raise ValidationError(f"Invalid pixel anim 0x{anim:02x}")
        slot = PixelSlot(rgb=rgb, anim=anim, pixel_speed=pixel_speed)
        with self._lock:
            self._slots = [slot] * self._count

    def fill_segment(self, start: int, end: int, r: int, g: int, b: int) -> None:
        """Fill inclusive range ``start..end`` with ``(r, g, b)``."""
        self._validate_index(start)
        self._validate_index(end)
        if start > end:
            raise ValidationError(f"start ({start}) must be <= end ({end})")
        rgb = validate_rgb(r, g, b)
        slot = PixelSlot(rgb=rgb)
        with self._lock:
            for i in range(start, end + 1):
                self._slots[i] = slot

    def clear(self) -> None:
        self.fill(0, 0, 0)

    def set_all_rgb(self, colors: Sequence[RGB]) -> None:
        if len(colors) != self._count:
            raise ValidationError(f"Expected {self._count} RGB tuples, got {len(colors)}")
        validated = [PixelSlot(rgb=validate_rgb(r, g, b)) for r, g, b in colors]
        with self._lock:
            self._slots = validated

    def apply_gradient(self, stops: list[RGB], start: int = 0, end: int | None = None) -> None:
        stop_idx = self._count - 1 if end is None else end
        self._validate_index(start)
        self._validate_index(stop_idx)
        if start > stop_idx:
            raise ValidationError("start must be <= end")
        sampled = gradient_rgb(stops, stop_idx - start + 1)
        with self._lock:
            for offset, rgb in enumerate(sampled):
                self._slots[start + offset] = PixelSlot(rgb=rgb)

    def rotate(self, steps: int = 1) -> None:
        with self._lock:
            if not self._slots:
                return
            k = steps % self._count
            if k:
                self._slots = self._slots[-k:] + self._slots[:-k]

    def snapshot(self, apply_brightness: bool = True) -> list[PixelSlot]:
        with self._lock:
            if not apply_brightness or self._brightness == 1.0:
                return list(self._slots)
            b = self._brightness
            return [
                PixelSlot(rgb=scale_rgb(s.rgb, b), anim=s.anim, pixel_speed=s.pixel_speed)
                for s in self._slots
            ]

    def snapshot_rgb(self, apply_brightness: bool = True) -> list[RGB]:
        return [s.rgb for s in self.snapshot(apply_brightness=apply_brightness)]
