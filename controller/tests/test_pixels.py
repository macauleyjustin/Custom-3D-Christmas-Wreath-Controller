"""Unit tests for color conversion, brightness scaling, framebuffer, and mapping."""

from __future__ import annotations

import unittest

from controller.exceptions import ValidationError
from controller.pixels.color import gradient_rgb, hsv_bytes_to_rgb, rgb_to_hsv_bytes, scale_rgb
from controller.pixels.framebuffer import PixelFrameBuffer
from controller.pixels.mapping import LogicalToPhysicalMapper
from controller.pixels.wreath_layout import build_wreath_layout


class PixelAndColorTests(unittest.TestCase):
    def test_rgb_hsv_round_trip(self) -> None:
        self.assertEqual(rgb_to_hsv_bytes(255, 0, 0), (0, 100, 100))
        self.assertEqual(rgb_to_hsv_bytes(0, 255, 0), (60, 100, 100))
        self.assertEqual(rgb_to_hsv_bytes(0, 0, 255), (120, 100, 100))
        self.assertEqual(rgb_to_hsv_bytes(255, 255, 255), (0, 0, 100))
        self.assertEqual(hsv_bytes_to_rgb(60, 100, 100), (0, 255, 0))
        self.assertEqual(scale_rgb((200, 100, 50), 0.5), (100, 50, 25))

    def test_framebuffer_operations_and_bounds(self) -> None:
        fb = PixelFrameBuffer(count=50)
        fb.fill(100, 200, 50)
        fb.set_pixel(0, 255, 0, 0)
        fb.set_brightness(0.5)
        snap = fb.snapshot_rgb(apply_brightness=True)
        self.assertEqual(len(snap), 50)
        self.assertEqual(snap[0], (128, 0, 0))
        self.assertEqual(snap[1], (50, 100, 25))

        fb.apply_gradient([(255, 0, 0), (0, 0, 255)], start=0, end=4)
        snap_unscaled = fb.snapshot_rgb(apply_brightness=False)
        self.assertEqual(snap_unscaled[0], (255, 0, 0))
        self.assertEqual(snap_unscaled[2], (128, 0, 128))
        self.assertEqual(snap_unscaled[4], (0, 0, 255))

        with self.assertRaises(ValidationError):
            fb.set_pixel(50, 255, 0, 0)
        with self.assertRaises(ValidationError):
            fb.set_pixel(0, 256, 0, 0)
        with self.assertRaises(ValidationError):
            fb.set_brightness(1.2)

    def test_logical_to_physical_mapping(self) -> None:
        mapper_cw = LogicalToPhysicalMapper(led_count=50, origin=10, reverse=False)
        self.assertEqual(mapper_cw.logical_to_physical(0), 10)
        self.assertEqual(mapper_cw.logical_to_physical(49), 9)
        self.assertEqual(mapper_cw.physical_to_logical(10), 0)

        mapper_ccw = LogicalToPhysicalMapper(led_count=50, origin=5, reverse=True)
        self.assertEqual(mapper_ccw.logical_to_physical(0), 5)
        self.assertEqual(mapper_ccw.logical_to_physical(1), 4)
        self.assertEqual(mapper_ccw.logical_to_physical(6), 49)

        fb = PixelFrameBuffer(count=50)
        fb.set_pixel(0, 255, 0, 0)
        doodle = mapper_cw.to_doodle_pixels(fb.snapshot())
        self.assertEqual(doodle[10].hue_byte, 0)
        self.assertEqual(doodle[10].val, 100)

        groups = mapper_cw.to_compact_groups(fb.snapshot())
        self.assertEqual(len(groups), 20)

    def test_gradient_rgb(self) -> None:
        grad = gradient_rgb([(0, 0, 0), (100, 200, 50)], 3)
        self.assertEqual(grad, [(0, 0, 0), (50, 100, 25), (100, 200, 50)])

    def test_wreath_3d_layout_observed_nodes(self) -> None:
        nodes = build_wreath_layout(50)
        self.assertEqual(len(nodes), 50)
        mapped_count = sum(1 for n in nodes if n.mapped_from_user)
        self.assertEqual(mapped_count, 44)
        self.assertEqual(nodes[9].layer, "outer")
        self.assertEqual(nodes[9].clock_hour, 12.0)
        self.assertEqual(nodes[19].layer, "inner")
        self.assertEqual(nodes[23].layer, "inner")
        self.assertEqual(nodes[37].layer, "outer")
        self.assertEqual(nodes[37].clock_hour, 6.0)
        self.assertLess(nodes[37].y, -0.95)  # 6 o'clock bottom
        self.assertGreater(nodes[9].y, 0.95)  # 12 o'clock top
        self.assertEqual(nodes[42].layer, "front")
        self.assertEqual(nodes[49].layer, "inner")
        self.assertFalse(nodes[0].mapped_from_user)
