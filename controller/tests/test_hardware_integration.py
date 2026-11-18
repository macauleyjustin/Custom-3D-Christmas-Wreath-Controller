"""Live hardware integration tests (runs against real wreath if present on LAN)."""

from __future__ import annotations

import os
import time
import unittest

from controller.devices.wreath import WreathController
from controller.discovery.wifi_discovery import discover_wifi_devices
from controller.exceptions import UnsupportedCapabilityError
from controller.protocol.constants import MODE_COMPACT_COLOR, MODE_DOODLE, MODE_SCENE


def _resolve_live_ip() -> str | None:
    env_ip = os.environ.get("HL_TEST_IP", "").strip()
    if env_ip:
        return env_ip
    found = discover_wifi_devices(timeout=1.5, enrich_at_info=False)
    return found[0].ip if found else None


class HardwareIntegrationTests(unittest.TestCase):
    live_ip: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.live_ip = _resolve_live_ip()
        if not cls.live_ip:
            raise unittest.SkipTest("No Holiday Bright Lights hardware discovered on LAN")

    def test_live_wreath_end_to_end(self) -> None:
        assert self.live_ip is not None
        ctrl = WreathController(self.live_ip, target_fps=12.0)
        try:
            st = ctrl.connect()
            self.assertEqual(st.model_id, 0x6B)
            self.assertEqual(st.led_count, 50)

            rtc = ctrl.query_time()
            self.assertGreaterEqual(rtc.year, 2024)
            rc = ctrl.query_remote_config()
            self.assertEqual(rc.raw[0], 0x2B)

            ctrl.power_on()
            ctrl.set_color(0, 255, 0)
            time.sleep(0.2)
            st_c = ctrl.get_status()
            self.assertEqual(st_c.mode, MODE_COMPACT_COLOR)
            self.assertEqual(st_c.hue_byte, 60)

            # Verify 50-pixel Doodle mode
            ctrl.clear()
            for i in range(10):
                ctrl.set_pixel(i, 255, 0, 0)
                ctrl.set_pixel(10 + i, 0, 255, 0)
                ctrl.set_pixel(20 + i, 0, 0, 255)
                ctrl.set_pixel(30 + i, 255, 200, 0)
                ctrl.set_pixel(40 + i, 255, 255, 255)
            ctrl.show()
            time.sleep(0.2)
            st_d = ctrl.get_status()
            self.assertEqual(st_d.mode, MODE_DOODLE)

            # Verify host streaming at 12 FPS
            ctrl.set_effect("rotating_rainbow", speed=0.6)
            time.sleep(0.6)
            sched = ctrl.scheduler_stats()
            self.assertTrue(sched.running)
            self.assertGreaterEqual(sched.frames_sent, 5)
            self.assertEqual(sched.frames_dropped, 0)
            ctrl.stop_effect()

            # Verify native scene E1 21 and overlay E1 26
            ctrl.set_native_scene("native_meteor", speed_pct=70)
            time.sleep(0.2)
            st_n = ctrl.get_status()
            self.assertEqual(st_n.mode, MODE_SCENE)
            self.assertEqual(st_n.pattern, 0x02)

            with self.assertRaises(UnsupportedCapabilityError):
                ctrl.get_timers()

            # Leave wreath glowing in a pleasant rainbow gradient
            ctrl.framebuffer.apply_gradient([(255, 0, 0), (0, 255, 0), (0, 120, 255), (255, 0, 0)])
            ctrl.show()
        finally:
            ctrl.disconnect()
