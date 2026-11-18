"""High-level public WreathController API uniting transport, protocol, pixels, and scheduler."""

from __future__ import annotations

import threading
from typing import Any, Optional, Sequence

from controller.devices.capabilities import DeviceCapabilities, capabilities_for_model
from controller.diagnostics.capture import PacketCaptureLog
from controller.discovery.wifi_discovery import query_module_at_info
from controller.effects.base import HostEffect, TimelineAnimation
from controller.effects.library import KeyframeSequenceEffect, create_host_effect
from controller.effects.native import NativeScenePreset, get_native_scene
from controller.exceptions import UnsupportedCapabilityError, ValidationError
from controller.pixels.color import RGB, rgb_to_hsv_bytes, scale_rgb, validate_rgb
from controller.pixels.framebuffer import PixelFrameBuffer
from controller.pixels.mapping import LogicalToPhysicalMapper
from controller.protocol.commands.color import (
    build_e0_global_color,
    build_e1_compact_color,
    build_e1_compact_solid,
)
from controller.protocol.commands.effects import build_e1_custom_scene
from controller.protocol.commands.pixels import (
    build_e1_doodle_frame,
    build_e1_frame_options,
)
from controller.protocol.commands.system import (
    build_power_command,
    build_remote_config_query,
    build_state_query,
    build_time_query,
)
from controller.protocol.constants import (
    DEFAULT_PIXEL_COUNT,
    DEFAULT_STREAM_FPS,
    MODEL_ID_WREATH_6B,
    PIXEL_ANIM_STATIC,
)
from controller.protocol.decoder.responses import (
    DeviceTime,
    ExtendedState,
    RemoteConfig,
    parse_extended_state,
    parse_remote_config,
    parse_time_response,
)
from controller.scheduler.engine import FrameScheduler, SchedulerStats
from controller.transports.base import BaseTransport, TransportStats
from controller.transports.wifi import WiFiTCPTransport


class WreathController:
    """Primary public interface for controlling a Holiday Bright Lights controller."""

    def __init__(
        self,
        host_or_transport: str | BaseTransport,
        *,
        port: int = 5577,
        led_count: int = DEFAULT_PIXEL_COUNT,
        mapper: Optional[LogicalToPhysicalMapper] = None,
        target_fps: float = DEFAULT_STREAM_FPS,
        capture: Optional[PacketCaptureLog] = None,
    ) -> None:
        self.capture = capture if capture is not None else PacketCaptureLog()
        if isinstance(host_or_transport, str):
            self.transport: BaseTransport = WiFiTCPTransport(
                host_or_transport, port=port, capture=self.capture
            )
        else:
            self.transport = host_or_transport
            if self.transport.capture is not self.capture:
                self.capture = self.transport.capture

        self._lock = threading.RLock()
        self._led_count = led_count
        self._framebuffer = PixelFrameBuffer(count=led_count)
        self._mapper = mapper if mapper is not None else LogicalToPhysicalMapper(led_count=led_count)
        self._scheduler = FrameScheduler(
            self._submit_scheduled_pixels,
            led_count=led_count,
            target_fps=target_fps,
        )

        self._last_state: ExtendedState | None = None
        self._capabilities: DeviceCapabilities = capabilities_for_model(
            MODEL_ID_WREATH_6B,
            led_count=led_count,
            transport_name=self.transport.name,
        )
        self._at_info: dict[str, str] = {}
        self._output_mode: str = "solid"  # "solid" | "doodle" | "native_scene" | "host_effect"
        self._solid_rgb: RGB = (255, 0, 0)
        self._solid_white: int = 0
        self._active_native_scene: NativeScenePreset | None = None
        self._active_native_speed: int = 50
        self._active_overlay: str | None = None

    @property
    def led_count(self) -> int:
        return self._led_count

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._capabilities

    @property
    def framebuffer(self) -> PixelFrameBuffer:
        return self._framebuffer

    @property
    def mapper(self) -> LogicalToPhysicalMapper:
        return self._mapper

    def set_mapping(self, *, origin: int = 0, reverse: bool = False) -> None:
        """Update logical-to-physical pixel ring mapping."""
        with self._lock:
            self._mapper = LogicalToPhysicalMapper(
                led_count=self._led_count, origin=origin, reverse=reverse
            )

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected

    def connect(self) -> ExtendedState:
        """Connect to the controller and query live ``EA 81`` hardware state."""
        self.transport.connect()
        state = self.get_status()
        if state.led_count > 0 and state.led_count != self._led_count:
            with self._lock:
                self._led_count = state.led_count
                self._framebuffer = PixelFrameBuffer(count=self._led_count)
                self._mapper = LogicalToPhysicalMapper(
                    led_count=self._led_count,
                    origin=min(self._mapper.origin, self._led_count - 1),
                    reverse=self._mapper.reverse,
                )
                self._scheduler.stop()
                self._scheduler = FrameScheduler(
                    self._submit_scheduled_pixels,
                    led_count=self._led_count,
                    target_fps=self._scheduler.stats().target_fps,
                )
        self._capabilities = capabilities_for_model(
            state.model_id,
            led_count=self._led_count,
            transport_name=self.transport.name,
        )
        if self.transport.name == "wifi" and isinstance(self.transport, WiFiTCPTransport):
            self._at_info = query_module_at_info(self.transport.host, timeout=0.4)
        return state

    def disconnect(self) -> None:
        """Stop any running effect and close the transport cleanly."""
        self.stop_effect()
        self.transport.disconnect()

    def get_status(self) -> ExtendedState:
        """Query and decode the 27-byte ``0xEA 0x81`` controller state."""
        resp = self.transport.send_command(
            build_state_query(include_inner_checksum=(self.transport.name == "ble")),
            expect_response=True,
            expected_prefix=b"\xea\x81",
            idempotent=True,
        )
        assert resp is not None
        state = parse_extended_state(resp)
        with self._lock:
            self._last_state = state
        return state

    def query_time(self) -> DeviceTime:
        """Query the controller's onboard RTC (``0x11 0x1A 0x1B 0x0F``)."""
        resp = self.transport.send_command(
            build_time_query(include_inner_checksum=(self.transport.name == "ble")),
            expect_response=True,
            expected_prefix=b"\x0f\x11",
            idempotent=True,
        )
        assert resp is not None
        return parse_time_response(resp)

    def query_remote_config(self) -> RemoteConfig:
        """Query remote configuration (``0x2B 0x2C 0x2D``)."""
        resp = self.transport.send_command(
            build_remote_config_query(),
            expect_response=True,
            expected_prefix=b"\x2b",
            idempotent=True,
        )
        assert resp is not None
        return parse_remote_config(resp)

    def power_on(self) -> None:
        """Power the LEDs on (``0x71 0x23 0x0F``)."""
        self.transport.send_command(
            build_power_command(True, include_inner_checksum=(self.transport.name == "ble")),
            expect_response=False,
            idempotent=True,
        )

    def power_off(self) -> None:
        """Stop any active host animation and power the LEDs off (``0x71 0x24 0x0F``)."""
        self.stop_effect()
        self.transport.send_command(
            build_power_command(False, include_inner_checksum=(self.transport.name == "ble")),
            expect_response=False,
            idempotent=True,
        )

    def set_brightness(self, level: float) -> None:
        """Set master brightness in ``0.0..1.0`` across active lighting modes."""
        self._framebuffer.set_brightness(level)
        with self._lock:
            mode = self._output_mode
            solid_rgb = self._solid_rgb
            solid_white = self._solid_white
            scene = self._active_native_scene
            scene_speed = self._active_native_speed

        if mode == "host_effect" and self._scheduler.is_running:
            return  # Next scheduled frame picks up updated framebuffer brightness
        if mode == "doodle":
            self.show()
            return
        if mode == "solid":
            self._send_solid(solid_rgb, white=solid_white, brightness=float(level))
            return
        if mode == "native_scene" and scene is not None:
            scaled_colors = [
                (h, s, round(v * float(level)), round(w * float(level)))
                for h, s, v, w in scene.colors
            ]
            payload = build_e1_custom_scene(
                scene.program,
                scaled_colors,
                speed=scene_speed,
                option_one=scene.option_one,
                option_two=scene.option_two,
                mode_param=scene.mode_param,
            )
            self.transport.send_command(payload, expect_response=False, idempotent=True)
            return
        raise UnsupportedCapabilityError(
            "Brightness scaling is unavailable for the current external controller mode"
        )

    def _send_solid(self, rgb: RGB, *, white: int, brightness: float) -> None:
        scaled = scale_rgb(rgb, brightness)
        h, s, v = rgb_to_hsv_bytes(*scaled)
        w_scaled = round(white * brightness)
        payload = build_e1_compact_solid(h, s, v, white_val=w_scaled)
        self.transport.send_command(payload, expect_response=False, idempotent=True)

    def set_color(
        self,
        r: int,
        g: int,
        b: int,
        *,
        white: int = 0,
        use_legacy_e0: bool = False,
    ) -> None:
        """Set the entire strand to a solid RGB color (and optional white channel 0..100)."""
        rgb = validate_rgb(r, g, b)
        if not 0 <= white <= 100:
            raise ValidationError(f"white must be in 0..100, got {white}")
        self.stop_effect()
        with self._lock:
            self._solid_rgb = rgb
            self._solid_white = white
            self._output_mode = "solid"
            self._active_native_scene = None
            brightness = self._framebuffer.brightness
        self._framebuffer.fill(*rgb)

        scaled = scale_rgb(rgb, brightness)
        h, s, v = rgb_to_hsv_bytes(*scaled)
        w_scaled = round(white * brightness)
        if use_legacy_e0:
            payload = build_e0_global_color(h, s, v, white_temp=0 if w_scaled > 0 else 0, white_val=w_scaled)
        else:
            payload = build_e1_compact_solid(h, s, v, white_val=w_scaled)
        self.transport.send_command(payload, expect_response=False, idempotent=True)

    def set_zones(self, zones_rgb: Sequence[RGB], *, white: int = 0) -> None:
        """Set the 20 compact color zones directly using ``E1 22``."""
        if len(zones_rgb) != 20:
            raise ValidationError(f"E1 22 requires exactly 20 RGB zones, got {len(zones_rgb)}")
        self.stop_effect()
        b_level = self._framebuffer.brightness
        groups: list[tuple[int, int, int, int]] = []
        for r, g, b in zones_rgb:
            sr, sg, sb = scale_rgb(validate_rgb(r, g, b), b_level)
            h, s, v = rgb_to_hsv_bytes(sr, sg, sb)
            groups.append((h, s, v, round(white * b_level)))
        with self._lock:
            self._output_mode = "solid"
            self._active_native_scene = None
        self.transport.send_command(build_e1_compact_color(groups), expect_response=False, idempotent=True)

    def set_pixel(
        self,
        index: int,
        r: int,
        g: int,
        b: int,
        *,
        anim: int = PIXEL_ANIM_STATIC,
        pixel_speed: int = 100,
    ) -> None:
        """Set one logical pixel in the staging framebuffer (call :meth:`show` to push)."""
        self._framebuffer.set_pixel(index, r, g, b, anim=anim, pixel_speed=pixel_speed)

    def fill(self, r: int, g: int, b: int) -> None:
        """Fill all logical pixels in the staging framebuffer (call :meth:`show` to push)."""
        self._framebuffer.fill(r, g, b)

    def clear(self) -> None:
        """Set all logical pixels in the staging framebuffer to black/off."""
        self._framebuffer.clear()

    def show(self, *, frame_speed: int = 100) -> None:
        """Flush the staging framebuffer to the wreath via ``E1 23``."""
        if not self._capabilities.supports_per_pixel_doodle:
            raise UnsupportedCapabilityError(
                f"Per-pixel E1 23 frame transmission is unsupported over {self.transport.name} "
                "(367B frame exceeds 244B BLE write-without-response MTU). Use Wi-Fi TCP 5577 or set_zones()."
            )
        self.stop_effect()
        self._flush_framebuffer(frame_speed=frame_speed)
        with self._lock:
            self._output_mode = "doodle"
            self._active_native_scene = None

    def _flush_framebuffer(self, *, frame_speed: int = 100) -> None:
        slots = self._framebuffer.snapshot(apply_brightness=True)
        doodle_pixels = self._mapper.to_doodle_pixels(slots)
        payload = build_e1_doodle_frame(doodle_pixels, speed=frame_speed)
        self.transport.send_command(payload, expect_response=False, idempotent=True)

    def _submit_scheduled_pixels(self, pixels: list[RGB]) -> None:
        self._framebuffer.set_all_rgb(pixels)
        self._flush_framebuffer(frame_speed=100)

    def set_effect(
        self,
        name: str,
        *,
        speed: float | None = None,
        target_fps: float | None = None,
        **params: Any,
    ) -> None:
        """Start a host-streamed per-pixel effect or controller-native ``native:<name>`` preset."""
        clean = name.strip()
        if clean.lower().startswith("native:"):
            preset_name = clean.split(":", 1)[1]
            pct = 50 if speed is None else round(max(0.0, min(1.0, float(speed))) * 100)
            self.set_native_scene(preset_name, speed_pct=pct)
            return
        if clean.lower().startswith("overlay:"):
            overlay_name = clean.split(":", 1)[1]
            pct = 75 if speed is None else round(max(0.0, min(1.0, float(speed))) * 100)
            self.set_doodle_overlay(overlay_name, speed_pct=pct)
            return

        if not self._capabilities.supports_per_pixel_doodle:
            raise UnsupportedCapabilityError(
                f"Host pixel streaming effects require Wi-Fi TCP; use 'native:<scene>' on {self.transport.name}."
            )
        effect: HostEffect = create_host_effect(clean, speed=speed, **params)
        with self._lock:
            self._output_mode = "host_effect"
            self._active_native_scene = None
        self._scheduler.start(effect, target_fps=target_fps)

    def play_timeline(self, timeline: TimelineAnimation, *, speed: float = 0.5, target_fps: float | None = None) -> None:
        """Stream a user-authored :class:`TimelineAnimation` through the FrameScheduler."""
        if not self._capabilities.supports_per_pixel_doodle:
            raise UnsupportedCapabilityError("Timeline pixel streaming requires Wi-Fi TCP 5577")
        effect = KeyframeSequenceEffect(timeline, speed=speed)
        with self._lock:
            self._output_mode = "host_effect"
            self._active_native_scene = None
        self._scheduler.start(effect, target_fps=target_fps)

    def set_native_scene(self, preset_id: str, *, speed_pct: int | None = None) -> None:
        """Activate a controller-native ``E1 21`` scene executed directly on the BL602."""
        self.stop_effect()
        scene = get_native_scene(preset_id)
        spd = scene.default_speed if speed_pct is None else int(speed_pct)
        if not 0 <= spd <= 100:
            raise ValidationError(f"speed_pct must be 0..100, got {spd}")
        b_level = self._framebuffer.brightness
        scaled_colors = [
            (h, s, round(v * b_level), round(w * b_level)) for h, s, v, w in scene.colors
        ]
        payload = build_e1_custom_scene(
            scene.program,
            scaled_colors,
            speed=spd,
            option_one=scene.option_one,
            option_two=scene.option_two,
            mode_param=scene.mode_param,
        )
        with self._lock:
            self._output_mode = "native_scene"
            self._active_native_scene = scene
            self._active_native_speed = spd
        self.transport.send_command(payload, expect_response=False, idempotent=True)

    def set_doodle_overlay(self, option: str | int, *, speed_pct: int = 75) -> None:
        """Apply a controller-native ``E1 26`` dynamic animation overlay to current pixels."""
        self.stop_effect()
        payload = build_e1_frame_options(option, speed=speed_pct)
        with self._lock:
            self._output_mode = "doodle"
            self._active_overlay = str(option)
        self.transport.send_command(payload, expect_response=False, idempotent=True)

    def set_speed(self, speed: float) -> None:
        """Adjust speed (``0.0..1.0``) for the running host effect or active native scene."""
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.0 <= float(speed) <= 1.0:
            raise ValidationError(f"speed must be in 0.0..1.0, got {speed!r}")
        if self._scheduler.is_running:
            self._scheduler.set_speed(float(speed))
            return
        with self._lock:
            scene = self._active_native_scene
            mode = self._output_mode
        if mode == "native_scene" and scene is not None:
            self.set_native_scene(scene.id, speed_pct=round(float(speed) * 100))
            return
        raise ValidationError("No active effect or native scene is running")

    def set_target_fps(self, fps: float) -> None:
        """Adjust streaming frame rate in ``1.0..18.0`` FPS."""
        self._scheduler.set_target_fps(fps)

    def stop_effect(self) -> None:
        """Stop any active host-side animation thread."""
        self._scheduler.stop()

    def send_raw_command(
        self,
        inner_bytes: bytes,
        *,
        expect_response: bool = False,
        allow_non_idempotent_retry: bool = False,
    ) -> bytes | None:
        """Developer console escape hatch for sending raw verified inner payloads."""
        if not inner_bytes:
            raise ValidationError("inner_bytes must not be empty")
        return self.transport.send_command(
            inner_bytes,
            expect_response=expect_response,
            idempotent=allow_non_idempotent_retry,
        )

    # --- Explicit unsupported capability guards ---
    def get_timers(self) -> Any:
        raise UnsupportedCapabilityError(
            "Timer table read (0x22 0x2A 0x2B 0x0F) is unsupported on AK001-ZJ21413 (0x6B): "
            "live device returned no response across wrapped/checksummed variants."
        )

    def get_power_restore_state(self) -> Any:
        raise UnsupportedCapabilityError(
            "Power-restore state query (0x32 0x3A 0x3B 0x0F) is unsupported on AK001-ZJ21413 (0x6B)."
        )

    def get_strip_ic_config(self) -> Any:
        raise UnsupportedCapabilityError(
            "Legacy A1/A3 strip IC query (0x63 0x12 0x21) is unsupported on 0x6B; "
            "LED count (50) is reported in EA 81 bytes 17-18."
        )

    def set_music_level(self, level: int) -> None:
        raise UnsupportedCapabilityError(
            "Music mode arm command (0xE1 0x24) is unverified on 0x6B; "
            "music streaming is intentionally not exposed."
        )

    def scheduler_stats(self) -> SchedulerStats:
        return self._scheduler.stats()

    def transport_stats(self) -> TransportStats:
        return self.transport.stats()

    def get_diagnostics(self) -> dict[str, Any]:
        """Collect complete connection, capability, state, and scheduler diagnostics."""
        state = self._last_state
        t_stats = self.transport.stats()
        s_stats = self._scheduler.stats()
        return {
            "endpoint": self.transport.endpoint,
            "transport": self.transport.name,
            "connected": t_stats.connected,
            "at_info": dict(self._at_info),
            "capabilities": {
                "model_id": f"0x{self._capabilities.model_id:02X}",
                "model_name": self._capabilities.model_name,
                "soc_family": self._capabilities.soc_family,
                "firmware_family": self._capabilities.firmware_family,
                "led_count": self._capabilities.led_count,
                "supports_per_pixel_doodle": self._capabilities.supports_per_pixel_doodle,
                "supports_compact_20_zones": self._capabilities.supports_compact_20_zones,
                "supports_native_scenes": self._capabilities.supports_native_scenes,
                "supports_ble_control": self._capabilities.supports_ble_control,
                "recommended_max_fps": self._capabilities.recommended_max_fps,
                "hard_max_fps": self._capabilities.hard_max_fps,
                "notes": list(self._capabilities.notes),
            },
            "state": None
            if state is None
            else {
                "is_on": state.is_on,
                "mode": state.mode_name,
                "mode_byte": f"0x{state.mode:02x}",
                "pattern_byte": f"0x{state.pattern:02x}",
                "speed": state.speed,
                "hue_byte": state.hue_byte,
                "saturation": state.saturation,
                "value": state.value,
                "white_temp": state.white_temp,
                "white_brightness": state.white_brightness,
                "led_count": state.led_count,
                "fw_subversion": state.fw_subversion,
                "raw_hex": state.raw.hex(),
            },
            "transport_stats": t_stats.__dict__,
            "scheduler": s_stats.__dict__,
            "output_mode": self._output_mode,
            "brightness": self._framebuffer.brightness,
            "mapping": {
                "origin": self._mapper.origin,
                "reverse": self._mapper.reverse,
            },
        }
