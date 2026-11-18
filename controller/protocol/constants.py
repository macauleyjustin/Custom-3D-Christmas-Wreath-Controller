"""Verified protocol constants for Holiday Bright Lights AK001-ZJ21413 (0x6B)."""

from __future__ import annotations

# --- Network & Discovery ---
DEFAULT_TCP_PORT = 5577
DISCOVERY_UDP_PORT = 48899
DISCOVERY_QUERY = b"HF-A11ASSISTHREAD"
AT_LVER_QUERY = b"AT+LVER\r"
AT_SOCKB_QUERY = b"AT+SOCKB\r"
AT_WMODE_QUERY = b"AT+WMODE\r"

# --- BLE GATT (IOTWFC00) ---
BLE_DEVICE_NAME_PREFIX = "IOTWFC"
BLE_SERVICE_UUID = "FFFF"
BLE_WRITE_CHAR_UUID = "FF01"
BLE_NOTIFY_CHAR_UUID = "FF02"
BLE_PROVISION_SERVICE_UUID = "FE00"
BLE_SERVICE_DATA_UUID = "5A01"

# --- TCP Tunnel Framing (B0 B1 B2 B3) ---
TUNNEL_PREAMBLE = bytes((0xB0, 0xB1, 0xB2, 0xB3))
TUNNEL_FIXED_PREFIX = bytes((0x00, 0x01))
TUNNEL_VERSION_DEFAULT = 0x02
TUNNEL_VERSION_ALT = 0x01
TUNNEL_HEADER_LEN = 10  # 4B preamble + 2B fixed + 1B ver + 1B seq + 2B length
TUNNEL_MIN_FRAME_LEN = 11  # header + 1B checksum

# --- BLE v0 Framing ---
BLE_V0_FRAG_SINGLE = bytes((0x80, 0x00))
BLE_V0_CMD_EXPECT_RESPONSE = 0x0A
BLE_V0_CMD_NO_RESPONSE = 0x0B

# --- Verified Model & State Identifiers ---
MODEL_ID_WREATH_6B = 0x6B
MODEL_ID_INVISILIGHTS_6E = 0x6E
MODEL_ID_SURPLIFE_B6 = 0xB6
DEFAULT_PIXEL_COUNT = 50
COMPACT_COLOR_GROUP_COUNT = 20

# --- Verified Inner Opcodes ---
CMD_STATE_QUERY = bytes((0x81, 0x8A, 0x8B))
CMD_POWER_ON = bytes((0x71, 0x23, 0x0F))
CMD_POWER_OFF = bytes((0x71, 0x24, 0x0F))
CMD_TIME_QUERY = bytes((0x11, 0x1A, 0x1B, 0x0F))
CMD_REMOTE_QUERY = bytes((0x2B, 0x2C, 0x2D))

# Global Color (Legacy 0xE0 0x01 0x00 0xC1)
CMD_E0_GLOBAL_PREFIX = bytes((0xE0, 0x01, 0x00, 0xC1))
CMD_E0_GLOBAL_FOOTER = bytes((0x00, 0x00, 0x0A, 0x00, 0x00))

# Extended Family (0xE1)
CMD_E1_SCENE = 0x21          # Native / Custom scene
CMD_E1_COMPACT_COLOR = 0x22  # 20-group color & white control
CMD_E1_DOODLE_FRAME = 0x23   # Per-pixel HSV frame (50 x 7B records)
CMD_E1_FRAME_OPTIONS = 0x26  # Dynamic animation overlay on E1 23 frame

# Response Headers
RESP_EXTENDED_STATE = bytes((0xEA, 0x81))
RESP_TIME = bytes((0x0F, 0x11))
RESP_REMOTE_CONFIG = 0x2B

# Power Bytes
POWER_ON_BYTE = 0x23
POWER_OFF_BYTE = 0x24

# Observed Controller Modes in EA 81 byte[7]
MODE_COMPACT_COLOR = 0x24
MODE_SCENE = 0x25
MODE_DOODLE = 0x66

# Per-pixel animation byte in E1 23 7-byte pixel records
PIXEL_ANIM_STATIC = 0x00
PIXEL_ANIM_PULSE = 0x08
PIXEL_ANIM_BLINK = 0x10
VALID_PIXEL_ANIMS = frozenset({PIXEL_ANIM_STATIC, PIXEL_ANIM_PULSE, PIXEL_ANIM_BLINK})

# E1 26 Dynamic Frame Animation Options (maps OO -> EA81 pat = OO + 1)
FRAME_ANIM_OPTIONS: dict[str, int] = {
    "static": 0x00,
    "flowing": 0x01,
    "firefly": 0x04,
    "stars_wink": 0x07,
    "accumulate": 0x08,
    "chase_twinkling": 0x09,
    "chase_melting": 0x0A,
    "chase_lightning": 0x0B,
    "melting_twinkling": 0x0C,
    "twinkling_sparkles": 0x0D,
    "lightning_melting": 0x0E,
    "lightning_sparkles": 0x0F,
    "lightning": 0x10,
    "melting": 0x11,
    "twinkling_stars": 0x12,
    "sparkles": 0x1E,
}

# E1 21 Custom Scene Program IDs (verified MM values)
SCENE_PROGRAMS: dict[str, int] = {
    "static_fill": 0x66,
    "wave": 0x01,
    "meteor": 0x02,
    "streamer": 0x03,
    "building_blocks": 0x04,
    "flowing_water": 0x05,
    "chase": 0x06,
    "horse_racing": 0x07,
    "cycle": 0x08,
    "breathe": 0x09,
    "jump": 0x0A,
    "strobe": 0x0B,
    "firefly": 0x0C,
    "stars_wink": 0x0D,
    "warning": 0x0E,
    "collision": 0x0F,
    "fireworks": 0x10,
    "comet": 0x11,
    "volcano": 0x13,
    "superluminal": 0x14,
    "rainbow_bridge": 0x15,
    "gradient_overlay": 0x16,
    "gradient_meteor": 0x18,
    "chase_twinkling": 0x30,
    "chase_melting": 0x31,
    "chase_lightning": 0x32,
    "melting_twinkling": 0x3C,
    "twinkling_sparkles": 0x3D,
    "lightning_melting": 0x3E,
    "lightning_sparkles": 0x3F,
    "lightning": 0x40,
    "melting": 0x41,
    "twinkling_stars": 0x42,
    "sparkles": 0x43,
    "galaxy": 0x44,
    "static_gradient": 0x65,
}

# Verified Hardware Performance Bounds (measured against 10.0.0.207 BL602)
RECOMMENDED_MAX_FPS = 15.0
HARD_MAX_FPS = 18.0
DEFAULT_STREAM_FPS = 12.0
