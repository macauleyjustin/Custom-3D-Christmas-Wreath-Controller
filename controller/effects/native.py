"""Controller-native E1 21 scene presets and E1 26 Doodle frame overlays."""

from __future__ import annotations

from dataclasses import dataclass

from controller.exceptions import ValidationError
from controller.protocol.constants import FRAME_ANIM_OPTIONS, SCENE_PROGRAMS


@dataclass(frozen=True)
class NativeScenePreset:
    """Built-in hardware-executed E1 21 scene preset."""

    id: str
    name: str
    program: int
    colors: tuple[tuple[int, int, int, int], ...]
    default_speed: int = 50
    option_one: int = 0x00
    option_two: int = 0x01
    mode_param: int = 0x64


NATIVE_SCENE_PRESETS: dict[str, NativeScenePreset] = {
    "native_candy_cane": NativeScenePreset(
        "native_candy_cane",
        "Candy Cane (Native)",
        SCENE_PROGRAMS["static_fill"],
        ((0, 100, 100, 0), (0, 0, 100, 0)),
        default_speed=80,
    ),
    "native_christmas": NativeScenePreset(
        "native_christmas",
        "Christmas (Native)",
        SCENE_PROGRAMS["chase"],
        ((0, 100, 100, 0), (60, 100, 100, 0), (0, 0, 100, 0)),
        default_speed=65,
    ),
    "native_meteor": NativeScenePreset(
        "native_meteor",
        "Meteor Shower (Native)",
        SCENE_PROGRAMS["meteor"],
        ((0, 100, 100, 0), (22, 100, 100, 0), (60, 100, 100, 0), (120, 100, 100, 0)),
        default_speed=75,
        option_one=0x02,
        option_two=0x01,
    ),
    "native_wave": NativeScenePreset(
        "native_wave",
        "Ocean Wave (Native)",
        SCENE_PROGRAMS["wave"],
        ((90, 100, 100, 0), (120, 100, 100, 0), (140, 80, 100, 0)),
        default_speed=60,
    ),
    "native_firefly": NativeScenePreset(
        "native_firefly",
        "Firefly Night (Native)",
        SCENE_PROGRAMS["firefly"],
        ((24, 100, 100, 0), (60, 90, 80, 0)),
        default_speed=60,
        option_one=0x01,
    ),
    "native_stars_wink": NativeScenePreset(
        "native_stars_wink",
        "Starry Night (Native)",
        SCENE_PROGRAMS["stars_wink"],
        ((120, 100, 100, 0), (150, 80, 100, 0), (0, 0, 100, 0)),
        default_speed=60,
        option_one=0x02,
    ),
    "native_fireworks": NativeScenePreset(
        "native_fireworks",
        "Dream Fireworks (Native)",
        SCENE_PROGRAMS["fireworks"],
        ((0, 100, 100, 0), (30, 100, 100, 0), (90, 100, 100, 0), (150, 100, 100, 0)),
        default_speed=70,
    ),
    "native_rainbow_bridge": NativeScenePreset(
        "native_rainbow_bridge",
        "Rainbow Bridge (Native)",
        SCENE_PROGRAMS["rainbow_bridge"],
        ((0, 100, 100, 0), (30, 100, 100, 0), (60, 100, 100, 0), (90, 100, 100, 0), (120, 100, 100, 0), (150, 100, 100, 0)),
        default_speed=65,
    ),
    "native_galaxy": NativeScenePreset(
        "native_galaxy",
        "Galaxy (Native)",
        SCENE_PROGRAMS["galaxy"],
        ((120, 100, 100, 0), (150, 100, 100, 0), (170, 90, 100, 0)),
        default_speed=55,
    ),
    "native_warning": NativeScenePreset(
        "native_warning",
        "Warning Pulse (Native)",
        SCENE_PROGRAMS["warning"],
        ((0, 100, 100, 0), (14, 100, 100, 0)),
        default_speed=70,
    ),
}

NATIVE_FRAME_OVERLAYS: dict[str, int] = dict(FRAME_ANIM_OPTIONS)


def list_native_scenes() -> list[dict[str, object]]:
    """Return metadata for verified E1 21 native scenes and raw programs."""
    items: list[dict[str, object]] = []
    for preset in NATIVE_SCENE_PRESETS.values():
        items.append(
            {
                "id": preset.id,
                "name": preset.name,
                "program": preset.program,
                "default_speed": preset.default_speed,
            }
        )
    return items


def list_native_overlays() -> list[dict[str, object]]:
    """Return verified E1 26 frame animation overlays for E1 23 pixel frames."""
    return [{"id": k, "oo": v} for k, v in NATIVE_FRAME_OVERLAYS.items()]


def get_native_scene(preset_id: str) -> NativeScenePreset:
    key = preset_id.strip().lower().replace(" ", "_").replace("-", "_")
    if key in NATIVE_SCENE_PRESETS:
        return NATIVE_SCENE_PRESETS[key]
    if key in SCENE_PROGRAMS:
        return NativeScenePreset(
            id=key,
            name=key.replace("_", " ").title(),
            program=SCENE_PROGRAMS[key],
            colors=((0, 100, 100, 0), (60, 100, 100, 0), (120, 100, 100, 0)),
            default_speed=50,
        )
    raise ValidationError(f"Unknown native scene preset: {preset_id!r}")
