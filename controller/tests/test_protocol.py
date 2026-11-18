"""Unit tests for protocol framing, checksums, builders, and response decoders."""

from __future__ import annotations

import unittest

from controller.discovery.ble_discovery import parse_5a01_service_data
from controller.discovery.wifi_discovery import parse_discovery_reply
from controller.exceptions import ProtocolError, ValidationError
from controller.protocol.commands.color import build_e0_global_color, build_e1_compact_color, build_e1_compact_solid
from controller.protocol.commands.effects import build_e1_custom_scene
from controller.protocol.commands.pixels import DoodlePixel, build_e1_doodle_frame, build_e1_frame_options, decode_e1_doodle_frame
from controller.protocol.commands.system import build_power_command, build_state_query
from controller.protocol.constants import MODE_COMPACT_COLOR, MODE_SCENE, MODEL_ID_WREATH_6B
from controller.protocol.decoder.responses import (
    decode_ble_notification,
    extract_tunnel_frames,
    parse_extended_state,
    parse_remote_config,
    parse_time_response,
)
from controller.protocol.encoder.tunnel import calculate_sum_checksum, wrap_ble_v0, wrap_tcp_tunnel
from controller.tests.fixtures import (
    FIXTURE_BLE_5A01_HEX,
    FIXTURE_BLE_NOTIFY_BLUE80,
    FIXTURE_TCP_REMOTE_RX,
    FIXTURE_TCP_STATE_GREEN_RX,
    FIXTURE_TCP_STATE_QUERY_RX,
    FIXTURE_TCP_STATE_QUERY_TX,
    FIXTURE_TCP_TIME_RX,
    FIXTURE_UDP_DISCOVERY,
)


class ProtocolTests(unittest.TestCase):
    def test_tunnel_wrap_matches_live_tx_fixture_and_plus198_equivalence(self) -> None:
        inner = build_state_query()
        pkt = wrap_tcp_tunnel(inner, seq=0)
        self.assertEqual(pkt, FIXTURE_TCP_STATE_QUERY_TX)
        # Verify sum(data_block_without_B0B1B2B3) + 198 == sum(all_bytes_with_B0B1B2B3) mod 256
        legacy_cs = (sum(pkt[4:-1]) + 198) % 256
        self.assertEqual(legacy_cs, pkt[-1])
        self.assertEqual(calculate_sum_checksum(pkt[:-1]), pkt[-1])

    def test_partial_stream_extraction_and_corrupt_checksum(self) -> None:
        buf = bytearray(FIXTURE_TCP_STATE_QUERY_RX[:12])
        self.assertEqual(extract_tunnel_frames(buf), [])
        buf.extend(FIXTURE_TCP_STATE_QUERY_RX[12:])
        buf.extend(FIXTURE_TCP_TIME_RX)
        frames = extract_tunnel_frames(buf)
        self.assertEqual(len(frames), 2)
        self.assertEqual(len(buf), 0)

        st = parse_extended_state(frames[0].inner)
        self.assertEqual(st.model_id, MODEL_ID_WREATH_6B)
        self.assertTrue(st.is_on)
        self.assertEqual(st.mode, MODE_SCENE)
        self.assertEqual(st.led_count, 50)

        tm = parse_time_response(frames[1].inner)
        self.assertEqual(tm.isoformat(), "2026-11-18T12:17:21")

        bad = bytearray(FIXTURE_TCP_STATE_QUERY_RX)
        bad[-1] ^= 0x01
        with self.assertRaises(ProtocolError):
            extract_tunnel_frames(bad)

    def test_green_state_and_remote_config_fixtures(self) -> None:
        buf = bytearray(FIXTURE_TCP_STATE_GREEN_RX)
        frames = extract_tunnel_frames(buf)
        st = parse_extended_state(frames[0].inner)
        self.assertEqual(st.mode, MODE_COMPACT_COLOR)
        self.assertEqual((st.hue_byte, st.saturation, st.value), (60, 100, 100))
        self.assertEqual(st.rgb, (0, 255, 0))

        rbuf = bytearray(FIXTURE_TCP_REMOTE_RX)
        rframes = extract_tunnel_frames(rbuf)
        rc = parse_remote_config(rframes[0].inner)
        self.assertEqual((rc.state_flag, rc.remote_mode), (3, 1))

    def test_ble_v0_wrap_and_notification_decode(self) -> None:
        pkt = wrap_ble_v0(bytes.fromhex("818a8b96"), seq=1, expect_response=True)
        self.assertEqual(pkt.hex(), "000180000004050a818a8b96")
        decoded = decode_ble_notification(FIXTURE_BLE_NOTIFY_BLUE80)
        assert decoded is not None
        st = parse_extended_state(decoded)
        self.assertEqual((st.hue_byte, st.saturation, st.value), (120, 100, 80))

    def test_discovery_parsers(self) -> None:
        wifi = parse_discovery_reply(FIXTURE_UDP_DISCOVERY)
        assert wifi is not None
        self.assertEqual(wifi.ip, "10.0.0.207")
        self.assertEqual(wifi.formatted_mac, "B4:E8:42:A7:FC:00")
        self.assertEqual(wifi.model, "AK001-ZJ21413")

        ble_meta = parse_5a01_service_data(bytes.fromhex(FIXTURE_BLE_5A01_HEX))
        self.assertEqual(ble_meta["mac"], "B4:E8:42:A7:FC:00")
        self.assertEqual(ble_meta["model_id"], 0x6B)
        self.assertEqual(ble_meta["fw_minor"], 30)

    def test_command_builders_and_bounds(self) -> None:
        self.assertEqual(build_power_command(True), b"\x71\x23\x0f")
        self.assertEqual(build_power_command(False), b"\x71\x24\x0f")
        self.assertEqual(len(build_e0_global_color(60, 100, 100)), 14)
        self.assertEqual(len(build_e1_compact_solid(60, 100, 100)), 107)
        self.assertEqual(len(build_e1_frame_options("firefly", speed=50)), 51)
        scene = build_e1_custom_scene("meteor", [(0, 100, 100, 0), (60, 100, 100, 0)], speed=65)
        self.assertEqual(len(scene), 16 + 10)

        pixels = [DoodlePixel(hue_byte=(i * 3) % 180, sat=100, val=100) for i in range(50)]
        frame = build_e1_doodle_frame(pixels, speed=75)
        self.assertEqual(len(frame), 9 + 50 * 7)
        spd, decoded_px = decode_e1_doodle_frame(frame)
        self.assertEqual(spd, 75)
        self.assertEqual(decoded_px, pixels)

        with self.assertRaises(ValidationError):
            build_e0_global_color(181)
        with self.assertRaises(ValidationError):
            build_e1_compact_color([(0, 100, 100, 0)] * 19)
        with self.assertRaises(ValidationError):
            DoodlePixel(hue_byte=0, anim=0x99).encode()
        with self.assertRaises(ValidationError):
            build_e1_doodle_frame([], speed=50)
