"""Host-streamed per-pixel effects, native presets, telegraphy, and weather sync."""

from controller.effects.base import EffectInfo, HostEffect, Keyframe, TimelineAnimation
from controller.effects.library import (
    HOST_EFFECT_CATALOG,
    KeyframeSequenceEffect,
    create_host_effect,
    list_host_effects,
)
from controller.effects.native import (
    NATIVE_FRAME_OVERLAYS,
    NATIVE_SCENE_PRESETS,
    NativeScenePreset,
    list_native_overlays,
    list_native_scenes,
)

__all__ = [
    "EffectInfo",
    "HOST_EFFECT_CATALOG",
    "HostEffect",
    "Keyframe",
    "KeyframeSequenceEffect",
    "NATIVE_FRAME_OVERLAYS",
    "NATIVE_SCENE_PRESETS",
    "NativeScenePreset",
    "TimelineAnimation",
    "create_host_effect",
    "list_host_effects",
    "list_native_overlays",
    "list_native_scenes",
]
