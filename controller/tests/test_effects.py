"""Unit tests for host-side effects, timelines, telegraphy, and weather mapping."""

from __future__ import annotations

import unittest

from controller.effects.base import Keyframe, TimelineAnimation
from controller.effects.library import (
    HOST_EFFECT_CATALOG,
    KeyframeSequenceEffect,
    create_host_effect,
)
from controller.effects.telegraphy import encode_binary_timeline, encode_morse_timeline
from controller.effects.weather_sync import map_wmo_weather
from controller.exceptions import ValidationError


class EffectsTests(unittest.TestCase):
    def test_all_host_effects_render_valid_frames(self) -> None:
        for effect_id in HOST_EFFECT_CATALOG:
            fx = create_host_effect(effect_id, speed=0.6)
            for step in range(5):
                frame = fx.render(50, elapsed_s=step * 0.25, frame_index=step)
                self.assertEqual(len(frame), 50, msg=effect_id)
                for r, g, b in frame:
                    self.assertTrue(0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255)

        with self.assertRaises(ValidationError):
            create_host_effect("nonexistent_effect")

    def test_timeline_keyframe_interpolation_and_cut(self) -> None:
        tl = TimelineAnimation(
            name="Test",
            loop=True,
            keyframes=[
                Keyframe(pixels=[(200, 0, 0)] * 50, duration_ms=1000, transition="linear"),
                Keyframe(pixels=[(0, 200, 0)] * 50, duration_ms=1000, transition="cut"),
            ],
        )
        fx = KeyframeSequenceEffect(tl, speed=0.4285714)  # rate = 1.0x
        mid = fx.render(50, elapsed_s=0.5, frame_index=0)
        self.assertTrue(85 <= mid[0][0] <= 115)
        self.assertTrue(85 <= mid[0][1] <= 115)
        cut = fx.render(50, elapsed_s=1.2, frame_index=1)
        self.assertEqual(cut[0], (0, 200, 0))

    def test_telegraphy_and_weather_mapping(self) -> None:
        morse = encode_morse_timeline("SOS", wpm=15.0)
        self.assertTrue(len(morse) > 10)
        binary = encode_binary_timeline("A", bps=2.0)
        # 'A' = 01000001 -> 8 bits x (bit + gap) = 16 steps
        self.assertEqual(len(binary), 16)
        self.assertEqual(map_wmo_weather(0).label, "Clear Sky")
        self.assertEqual(map_wmo_weather(73).recommended_effect, "snowfall")
        self.assertEqual(map_wmo_weather(95).recommended_effect, "thunderstorm")
