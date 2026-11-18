"""Verified hardware and protocol capability declarations."""

from __future__ import annotations

from dataclasses import dataclass

from controller.protocol.constants import (
    DEFAULT_PIXEL_COUNT,
    HARD_MAX_FPS,
    MODEL_ID_WREATH_6B,
    RECOMMENDED_MAX_FPS,
)


@dataclass(frozen=True)
class DeviceCapabilities:
    """Explicit capability manifest derived from verified hardware/protocol evidence."""

    model_id: int
    model_name: str
    soc_family: str
    firmware_family: str
    led_count: int
    compact_group_count: int
    supports_power: bool
    supports_global_hsvw: bool
    supports_compact_20_zones: bool
    supports_per_pixel_doodle: bool
    supports_frame_animation_overlay: bool
    supports_native_scenes: bool
    supports_rtc_time_query: bool
    supports_remote_config_query: bool
    supports_timers: bool
    supports_power_restore_config: bool
    supports_strip_ic_reconfig: bool
    supports_music_mode: bool
    supports_ble_control: bool
    supports_ble_pixel_streaming: bool
    recommended_max_fps: float
    hard_max_fps: float
    notes: tuple[str, ...] = ()


def capabilities_for_model(
    model_id: int,
    *,
    led_count: int = DEFAULT_PIXEL_COUNT,
    transport_name: str = "wifi",
) -> DeviceCapabilities:
    """Build verified capability profile for ``model_id`` and active transport."""
    is_ble = transport_name == "ble"
    return DeviceCapabilities(
        model_id=model_id,
        model_name="Holiday Bright Lights Brilliant Wreath (AK001-ZJ21413)"
        if model_id == MODEL_ID_WREATH_6B
        else f"Zengge Extended Controller (0x{model_id:02X})",
        soc_family="Bouffalo Lab BL602 (32-bit RISC-V, Wi-Fi 4 + BLE 5.0)",
        firmware_family="6B_30_20240524_ZG-BL-SBL-02",
        led_count=led_count,
        compact_group_count=20,
        supports_power=True,
        supports_global_hsvw=True,
        supports_compact_20_zones=True,
        supports_per_pixel_doodle=(not is_ble),
        supports_frame_animation_overlay=True,
        supports_native_scenes=True,
        supports_rtc_time_query=True,
        supports_remote_config_query=True,
        supports_timers=False,               # 0x22 0x2A 0x2B 0x0F returned no response on 0x6B
        supports_power_restore_config=False, # 0x32 0x3A 0x3B 0x0F returned no response on 0x6B
        supports_strip_ic_reconfig=False,    # 0x63 0x12 0x21 returned no response on 0x6B
        supports_music_mode=False,           # E1 24 arm format unverified
        supports_ble_control=True,
        supports_ble_pixel_streaming=False,  # 367B E1 23 exceeds 244B BLE write-without-response MTU
        recommended_max_fps=RECOMMENDED_MAX_FPS if not is_ble else 0.0,
        hard_max_fps=HARD_MAX_FPS if not is_ble else 0.0,
        notes=(
            "50 individual HSV pixels verified physically via E1 23.",
            "TCP 5577 sustained streaming verified up to 18.7 fps (50 ms); 20 ms stalled controller.",
            "BLE 0xFFFF (FF01/FF02) verified for queries & compact color; Wi-Fi TCP recommended for pixel streaming.",
        ),
    )
