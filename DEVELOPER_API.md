# Developer Library API (`DEVELOPER_API.md`)

Importable Python package: `controller` (zero external dependencies).

---

## 1. Quick Start

```python
from controller import WreathController
from controller.discovery.wifi_discovery import discover_wifi_devices

# Discover on LAN
devices = discover_wifi_devices(timeout=2.0)
host = devices[0].ip if devices else "10.0.0.207"

ctrl = WreathController(host)
state = ctrl.connect()
print(f"Connected to 0x{state.model_id:02X} with {ctrl.led_count} LEDs")

ctrl.power_on()
ctrl.set_brightness(0.75)
ctrl.set_color(255, 0, 0)

# Per-pixel addressing (verified 50 LEDs)
ctrl.clear()
ctrl.set_pixel(0, 255, 0, 0)
ctrl.set_pixel(1, 0, 255, 0)
ctrl.set_pixel(2, 0, 0, 255)
ctrl.show()

# Real-time host effect streaming (non-blocking background thread)
ctrl.set_effect("rotating_rainbow", speed=0.6)
ctrl.set_speed(0.8)
ctrl.stop_effect()

ctrl.disconnect()
```

---

## 2. `WreathController` Public Methods

| Method | Signature | Behavior & Exceptions |
|---|---|---|
| `connect()` | `() -> ExtendedState` | Opens transport, queries `EA 81`, syncs `led_count` & `DeviceCapabilities` |
| `disconnect()` | `() -> None` | Stops `FrameScheduler` cleanly and closes transport |
| `get_status()` | `() -> ExtendedState` | Sends `81 8A 8B`, parses 27B `EA 81` state |
| `query_time()` | `() -> DeviceTime` | Sends `11 1A 1B 0F`, parses 12B `0F 11` RTC time |
| `query_remote_config()` | `() -> RemoteConfig` | Sends `2B 2C 2D`, parses 14B `2B` config |
| `power_on()` / `power_off()` | `() -> None` | Sends `71 23 0F` / `71 24 0F` (stops active effects on `power_off`) |
| `set_color()` | `(r, g, b, *, white=0, use_legacy_e0=False)` | Sets solid color via `E1 22` (or `E0 C1`). Raises `ValidationError` on bad RGB |
| `set_brightness()` | `(level: float)` | Scales active mode (`0.0..1.0`); raises `UnsupportedCapabilityError` if in unknown external scene |
| `set_zones()` | `(zones_rgb: Sequence[RGB], *, white=0)` | Sets 20 `E1 22` zones independently |
| `set_pixel()` | `(index, r, g, b, *, anim=0x00, pixel_speed=100)` | Updates staging `PixelFrameBuffer` (`anim`: `0x00`, `0x08`, `0x10`) |
| `fill()` / `clear()` | `(r, g, b)` / `()` | Fills or zeros staging `PixelFrameBuffer` |
| `show()` | `(*, frame_speed=100)` | Maps logical pixels & sends `E1 23` frame; raises `UnsupportedCapabilityError` on BLE |
| `set_mapping()` | `(*, origin=0, reverse=False)` | Updates `LogicalToPhysicalMapper` |
| `set_effect()` | `(name, *, speed=None, target_fps=None, **params)` | Starts host effect (`"rainbow"`, `"fire"`, etc.), `"native:<id>"`, or `"overlay:<id>"` |
| `play_timeline()` | `(timeline: TimelineAnimation, *, speed=0.5, target_fps=None)` | Plays multi-keyframe animation |
| `set_speed()` / `set_target_fps()` | `(speed)` / `(fps)` | Adjusts running speed (`0.0..1.0`) or FPS (`1.0..18.0`) |
| `stop_effect()` | `() -> None` | Joins & stops `FrameScheduler` worker thread |
| `send_raw_command()` | `(inner_bytes, *, expect_response=False, allow_non_idempotent_retry=False)` | Developer escape hatch |
| `get_diagnostics()` | `() -> dict` | Returns capabilities, `EA 81` state, transport & scheduler telemetry |

### Explicitly Guarded Unsupported Calls
`get_timers()`, `get_power_restore_state()`, `get_strip_ic_config()`, and `set_music_level()` raise `UnsupportedCapabilityError` with details of why `0x6B` firmware does not support them.

---

## 3. Transports & Simulator

- `WiFiTCPTransport(host, port=5577)` — Thread-safe socket I/O with stream framing & 1-shot idempotent reconnect.
- `BLETransport("IOTWFC00")` — macOS CoreBluetooth bridge using Zengge BLE v0 framing over GATT `0xFFFF` (`FF01`/`FF02`).
- `SimulatorTransport(SimulatedWreathDevice())` — Virtual `0x6B` controller for offline development & fault-injection testing (`fail_next_send`, `timeout_next_query`, `corrupt_next_checksum`, `simulated_latency_s`).
- `ControllerManager` — Manages multiple concurrent controllers and JSON preset files (`~/.holiday_bright_lights/`).

---

## 4. Custom Host Effects

Subclass `HostEffect` and pass to `FrameScheduler` (or call `render()` directly):

```python
from controller.effects.base import EffectInfo, HostEffect
from controller.pixels.color import RGB

class PulseRed(HostEffect):
    info = EffectInfo("pulse_red", "Pulse Red", "Custom", "Example", 0.5)
    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        v = round(127.5 * (1 + __import__("math").sin(elapsed_s * 3)))
        return [(v, 0, 0)] * count
```
