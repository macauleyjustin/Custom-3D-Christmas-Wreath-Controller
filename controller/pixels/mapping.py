"""Logical-to-physical LED mapping for circular wreaths and linear strands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from controller.exceptions import ValidationError
from controller.pixels.color import rgb_to_hsv_bytes
from controller.pixels.framebuffer import PixelSlot
from controller.protocol.commands.pixels import DoodlePixel
from controller.protocol.constants import COMPACT_COLOR_GROUP_COUNT, DEFAULT_PIXEL_COUNT


@dataclass
class LogicalToPhysicalMapper:
    """Maps logical ring indices ``0..led_count-1`` to physical strand indices.

    Attributes:
        led_count: Number of physical addressable LEDs (verified 50 on 0x6B wreath).
        origin: Physical index corresponding to logical index ``0`` (default ``0``).
        reverse: If True, logical indices step counter-clockwise around the ring.
    """

    led_count: int = DEFAULT_PIXEL_COUNT
    origin: int = 0
    reverse: bool = False

    def __post_init__(self) -> None:
        if self.led_count < 1:
            raise ValidationError(f"led_count must be positive, got {self.led_count}")
        if not 0 <= self.origin < self.led_count:
            raise ValidationError(f"origin must be in 0..{self.led_count - 1}, got {self.origin}")

    def logical_to_physical(self, logical_index: int) -> int:
        if not 0 <= logical_index < self.led_count:
            raise ValidationError(
                f"logical_index {logical_index} out of bounds 0..{self.led_count - 1}"
            )
        if self.reverse:
            return (self.origin - logical_index) % self.led_count
        return (self.origin + logical_index) % self.led_count

    def physical_to_logical(self, physical_index: int) -> int:
        if not 0 <= physical_index < self.led_count:
            raise ValidationError(
                f"physical_index {physical_index} out of bounds 0..{self.led_count - 1}"
            )
        if self.reverse:
            return (self.origin - physical_index) % self.led_count
        return (physical_index - self.origin) % self.led_count

    def map_slots(self, logical_slots: Sequence[PixelSlot]) -> list[PixelSlot]:
        if len(logical_slots) != self.led_count:
            raise ValidationError(
                f"Expected {self.led_count} logical slots, got {len(logical_slots)}"
            )
        physical: list[PixelSlot] = [PixelSlot()] * self.led_count
        for logical_idx, slot in enumerate(logical_slots):
            phys_idx = self.logical_to_physical(logical_idx)
            physical[phys_idx] = slot
        return physical

    def to_doodle_pixels(self, logical_slots: Sequence[PixelSlot]) -> list[DoodlePixel]:
        """Convert logical slots into physically ordered ``E1 23`` DoodlePixels."""
        physical_slots = self.map_slots(logical_slots)
        doodle: list[DoodlePixel] = []
        for slot in physical_slots:
            h, s, v = rgb_to_hsv_bytes(*slot.rgb)
            doodle.append(
                DoodlePixel(
                    hue_byte=h,
                    sat=s,
                    val=v,
                    anim=slot.anim,
                    pixel_speed=slot.pixel_speed,
                )
            )
        return doodle

    def to_compact_groups(
        self, logical_slots: Sequence[PixelSlot]
    ) -> list[tuple[int, int, int, int]]:
        """Downsample ``led_count`` physical pixels into 20 ``E1 22`` compact groups."""
        physical = self.map_slots(logical_slots)
        groups: list[tuple[int, int, int, int]] = []
        for g in range(COMPACT_COLOR_GROUP_COUNT):
            idx = min(self.led_count - 1, round(g * (self.led_count - 1) / (COMPACT_COLOR_GROUP_COUNT - 1)))
            h, s, v = rgb_to_hsv_bytes(*physical[idx].rgb)
            groups.append((h, s, v, 0))
        return groups
