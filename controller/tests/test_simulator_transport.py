"""Simulator transport, recovery, fault-injection, and WreathController API tests."""

from __future__ import annotations

import time
import unittest

from controller.devices.wreath import WreathController
from controller.exceptions import ProtocolError, TransportError, UnsupportedCapabilityError, ValidationError
from controller.protocol.constants import MODE_COMPACT_COLOR, MODE_DOODLE, MODE_SCENE
from controller.transports.simulator import SimulatedWreathDevice, SimulatorTransport


class ControllerAndSimulatorTests(unittest.TestCase):
    def test_full_controller_api_against_simulator(self) -> None:
        dev = SimulatedWreathDevice(led_count=50)
        ctrl = WreathController(SimulatorTransport(dev), target_fps=12.0)
        st = ctrl.connect()
        self.assertEqual(st.led_count, 50)
        self.assertTrue(st.is_on)

        ctrl.power_off()
        self.assertFalse(ctrl.get_status().is_on)
        ctrl.power_on()
        self.assertTrue(ctrl.get_status().is_on)

        ctrl.set_color(0, 255, 0)
        st_color = ctrl.get_status()
        self.assertEqual(st_color.mode, MODE_COMPACT_COLOR)
        self.assertEqual(st_color.hue_byte, 60)

        ctrl.set_brightness(0.5)
        self.assertEqual(ctrl.get_status().value, 50)

        ctrl.set_pixel(0, 255, 0, 0)
        ctrl.set_pixel(1, 0, 255, 0)
        ctrl.set_pixel(2, 0, 0, 255)
        ctrl.show()
        self.assertEqual(ctrl.get_status().mode, MODE_DOODLE)
        self.assertEqual(dev.pixels[0].hue_byte, 0)
        self.assertEqual(dev.pixels[1].hue_byte, 60)
        self.assertEqual(dev.pixels[2].hue_byte, 120)

        ctrl.set_effect("rotating_rainbow", speed=0.7)
        time.sleep(0.22)
        stats = ctrl.scheduler_stats()
        self.assertTrue(stats.running)
        self.assertGreaterEqual(stats.frames_sent, 2)
        ctrl.stop_effect()
        self.assertFalse(ctrl.scheduler_stats().running)

        ctrl.set_effect("native:native_meteor", speed=0.8)
        st_nat = ctrl.get_status()
        self.assertEqual(st_nat.mode, MODE_SCENE)
        self.assertEqual(st_nat.pattern, 0x02)
        self.assertEqual(st_nat.speed, 80)

        self.assertTrue(ctrl.query_time().year >= 2024)
        self.assertEqual(ctrl.query_remote_config().remote_mode, 1)

        # Unsupported capabilities raise explicit errors
        with self.assertRaises(UnsupportedCapabilityError):
            ctrl.get_timers()
        with self.assertRaises(UnsupportedCapabilityError):
            ctrl.get_power_restore_state()
        with self.assertRaises(UnsupportedCapabilityError):
            ctrl.get_strip_ic_config()
        with self.assertRaises(UnsupportedCapabilityError):
            ctrl.set_music_level(10)

        # Unsafe FPS rejected
        with self.assertRaises(ValidationError):
            ctrl.set_target_fps(30.0)

        ctrl.disconnect()

    def test_fault_injection_recovery_and_non_idempotent_guard(self) -> None:
        dev = SimulatedWreathDevice()
        ctrl = WreathController(SimulatorTransport(dev))
        ctrl.connect()

        # Idempotent command recovers cleanly across single socket drop
        dev.fail_next_send = True
        ctrl.set_color(0, 0, 255)
        self.assertEqual(ctrl.transport_stats().reconnects, 1)
        self.assertEqual(ctrl.get_status().hue_byte, 120)

        # Non-idempotent raw command does NOT duplicate on failure
        dev.fail_next_send = True
        with self.assertRaises(TransportError):
            ctrl.send_raw_command(b"\x71\x23\x0f", allow_non_idempotent_retry=False)

        # Checksum corruption raises ProtocolError
        dev.corrupt_next_checksum = True
        with self.assertRaises(ProtocolError):
            ctrl.get_status()

        # Timeout raises TransportError
        dev.timeout_next_query = True
        with self.assertRaises(TransportError):
            ctrl.get_status()

        ctrl.disconnect()
