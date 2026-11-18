"""Base classes for host-rendered pixel effects and timeline animations."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from controller.exceptions import ValidationError
from controller.pixels.color import RGB, validate_rgb


@dataclass(frozen=True)
class EffectInfo:
    """Metadata describing a host-side per-pixel effect."""

    id: str
    name: str
    category: str
    description: str
    default_speed: float = 0.5


@dataclass
class Keyframe:
    """Single keyframe in a user-authored timeline animation."""

    pixels: list[RGB]
    duration_ms: int = 500
    transition: str = "linear"  # "cut" or "linear"

    def __post_init__(self) -> None:
        if self.duration_ms < 50:
            raise ValidationError(f"duration_ms must be >= 50, got {self.duration_ms}")
        if self.transition not in ("cut", "linear"):
            raise ValidationError(f"transition must be 'cut' or 'linear', got {self.transition!r}")
        self.pixels = [validate_rgb(*c) for c in self.pixels]


@dataclass
class TimelineAnimation:
    """Ordered sequence of keyframes with loop control."""

    name: str
    keyframes: list[Keyframe] = field(default_factory=list)
    loop: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "loop": self.loop,
            "keyframes": [
                {
                    "duration_ms": kf.duration_ms,
                    "transition": kf.transition,
                    "pixels": [list(px) for px in kf.pixels],
                }
                for kf in self.keyframes
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineAnimation":
        kfs = [
            Keyframe(
                pixels=[tuple(px) for px in item["pixels"]],  # type: ignore[misc]
                duration_ms=int(item.get("duration_ms", 500)),
                transition=str(item.get("transition", "linear")),
            )
            for item in data.get("keyframes", [])
        ]
        return cls(
            name=str(data.get("name", "Custom Timeline")),
            keyframes=kfs,
            loop=bool(data.get("loop", True)),
        )


class HostEffect(abc.ABC):
    """Abstract base class for host-side per-pixel frame generators."""

    info: EffectInfo

    def __init__(self, *, speed: float = 0.5, **params: Any) -> None:
        self.speed = self._clamp_speed(speed)
        self.params = params

    @staticmethod
    def _clamp_speed(speed: float) -> float:
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.0 <= float(speed) <= 1.0:
            raise ValidationError(f"speed must be in 0.0..1.0, got {speed!r}")
        return float(speed)

    def set_speed(self, speed: float) -> None:
        self.speed = self._clamp_speed(speed)

    @abc.abstractmethod
    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        """Generate ``count`` RGB pixels for the current frame timestamp."""
