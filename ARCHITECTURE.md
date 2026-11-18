# System Architecture (`ARCHITECTURE.md`)

This document describes the complete software architecture of the **Holiday Bright Lights — Brilliant Wreath Controller** (`controller` package and CLI entry points).

---

## 1. Repository Layout

```text
Bouffalo-Lab-Limited-Led-Controller---Holiday-Bright-Lights/
├── controller/
│   ├── __init__.py                   # Public exports
│   ├── __main__.py                   # CLI & Web Console launcher (`python3 -m controller`)
│   ├── exceptions.py                 # Typed exception hierarchy
│   ├── discovery/
│   │   ├── wifi_discovery.py         # UDP 48899 HF-A11ASSISTHREAD + AT+LVER/SOCKB/WMODE
│   │   └── ble_discovery.py          # CoreBluetooth BLE scan & 0x5A01 parser
│   ├── transports/
│   │   ├── base.py                   # BaseTransport + TransportStats
│   │   ├── wifi.py                   # Thread-safe TCP 5577 transport + framing reader
│   │   ├── ble.py                    # BLE GATT 0xFFFF (FF01/FF02) transport
│   │   └── simulator.py              # SimulatedWreathDevice + fault-injectable SimulatorTransport
│   ├── protocol/
│   │   ├── constants.py              # Verified opcodes, model IDs, frame/scene tables, FPS bounds
│   │   ├── encoder/tunnel.py         # B0 B1 B2 B3 TCP wrapper, BLE v0 wrapper, checksums
│   │   ├── decoder/responses.py      # Stream frame extractor + EA81/0F11/2B/BLE JSON decoders
│   │   └── commands/
│   │       ├── system.py             # 818A8B, 71230F/71240F, 111A1B0F, 2B2C2D
│   │       ├── color.py              # E0 01 00 C1 & E1 22 (20-group compact color)
│   │       ├── pixels.py             # E1 23 (50-pixel Doodle frame) & E1 26 (frame options)
│   │       └── effects.py            # E1 21 (custom/native scenes)
│   ├── pixels/
│   │   ├── color.py                  # RGB <-> HSV(0..180,0..100,0..100), scaling, gradients
│   │   ├── framebuffer.py            # Thread-safe staging PixelFrameBuffer
│   │   ├── mapping.py                # LogicalToPhysicalMapper (ring origin, CW/CCW, 50->20 groups)
│   │   └── wreath_layout.py          # Custom 3D wreath topology (44 mapped clock+depth nodes, 50 total)
│   ├── effects/
│   │   ├── base.py                   # HostEffect ABC, Keyframe, TimelineAnimation
│   │   ├── library.py                # 38 host effects (incl. 12 3D physics/nature/experimental effects) + KeyframeSequenceEffect
│   │   ├── native.py                 # BL602-native E1 21 presets & E1 26 overlays
│   │   ├── telegraphy.py             # Morse code (PARIS WPM) & 8-bit ASCII binary encoders
│   │   └── weather_sync.py           # Open-Meteo stdlib urllib lookup & WMO mapper
│   ├── scheduler/
│   │   └── engine.py                 # Non-blocking FrameScheduler (1..18 FPS, default 12 FPS)
│   ├── devices/
│   │   ├── capabilities.py           # DeviceCapabilities manifest
│   │   ├── wreath.py                 # WreathController high-level API
│   │   └── manager.py                # ControllerManager (multi-device & JSON preset persistence)
│   ├── diagnostics/
│   │   ├── capture.py                # Thread-safe TX/RX PacketCaptureLog ring buffer & JSON export
│   │   └── probe.py                  # Discovery & hardware probe helpers
│   ├── ui/
│   │   ├── server.py                 # Pure-stdlib ThreadingHTTPServer REST/static console server
│   │   └── static/                   # Web Console SPA (index.html, styles.css, app.js)
│   └── tests/                        # Unit, simulator, Web API, and live hardware tests
├── controllights.py                  # Unified interactive CLI (refactored)
├── HLEffect.py                       # Backward-compatible CLI wrapper -> controllights
├── HLMasterEffects.py                # Backward-compatible CLI wrapper -> controllights
├── datasender.py                     # Morse / Binary optical telegraphy CLI
├── weather.py                        # Open-Meteo weather polling CLI
└── requirements.txt                  # Pure Python 3.10+ stdlib runtime
```

The original unedited repository scripts remain preserved at git tag `original-baseline`.

---

## 2. End-to-End Execution Chain

```text
User Interface (Web Console SPA / CLI)
   │
   ▼
Command Dispatcher (ui/server.py REST routes or WreathController methods)
   │  Validates bounds & capabilities (ValidationError / UnsupportedCapabilityError)
   ▼
Application State & Pixel Pipeline
   ├── Solid Color   ──▶ WreathController.set_color() ──▶ build_e1_compact_solid()
   ├── Pixel Buffer  ──▶ PixelFrameBuffer ──▶ LogicalToPhysicalMapper ──▶ build_e1_doodle_frame()
   ├── Host Effects  ──▶ FrameScheduler ──▶ HostEffect.render() ──▶ PixelFrameBuffer ──▶ E1 23
   └── Native Scenes ──▶ get_native_scene() ──▶ build_e1_custom_scene() (E1 21) / E1 26
   │
   ▼
Protocol Encoding (protocol/encoder/tunnel.py)
   ├── Wi-Fi / Sim: wrap_tcp_tunnel()  ──▶ B0 B1 B2 B3 00 01 02 <seq> <len2> <inner> <sum&FF>
   └── BLE:         wrap_ble_v0()      ──▶ 00 <seq> 80 00 <len2> <len+1> <0A|0B> <inner>
   │
   ▼
Transport Layer (transports/wifi.py | ble.py | simulator.py)
   ├── Acquires per-transport RLock, logs TX to PacketCaptureLog
   ├── Sends bytes over TCP 5577 or GATT 0xFFFF FF01
   └── Reads stream frames (extract_tunnel_frames) / FF02 JSON notifications
   │
   ▼
Response Decoding & State Sync (protocol/decoder/responses.py)
   └── Parses EA 81 ExtendedState, 0F 11 DeviceTime, or 2B RemoteConfig -> updates WreathController
```

---

## 3. Core Module Responsibilities

| Module | Key Functions / Classes | Caller | Inputs | Outputs / Hardware Interaction |
|---|---|---|---|---|
| `protocol/encoder/tunnel.py` | `wrap_tcp_tunnel`, `wrap_ble_v0`, `calculate_sum_checksum` | Transports, UI preview | Inner bytes, `seq` | Framed wire packets with mod-256 checksum |
| `protocol/decoder/responses.py` | `extract_tunnel_frames`, `decode_ble_notification`, `parse_extended_state`, `parse_time_response`, `parse_remote_config` | `WiFiTCPTransport`, `BLETransport`, `WreathController` | Raw stream `bytearray` or BLE notify bytes | Validated `TunnelFrame`, `ExtendedState`, `DeviceTime`, `RemoteConfig`; raises `ProtocolError` on bad checksum/header |
| `protocol/commands/*.py` | `build_state_query`, `build_power_command`, `build_e0_global_color`, `build_e1_compact_solid`, `build_e1_compact_color`, `build_e1_doodle_frame`, `build_e1_frame_options`, `build_e1_custom_scene` | `WreathController` | Validated HSV/pixel/scene args | Exact inner binary payloads |
| `transports/wifi.py` | `WiFiTCPTransport.connect`, `send_command`, `_read_matching_frame_locked` | `WreathController` | Inner command, `expect_response`, `idempotent` | TCP 5577 I/O with 1-retry reconnect for idempotent calls; raises `TransportError` on failure |
| `transports/ble.py` | `BLETransport.connect`, `send_command` | `WreathController` | Inner command | macOS CoreBluetooth Swift subprocess writing `FF01` and awaiting `FF02` notify |
| `transports/simulator.py` | `SimulatedWreathDevice`, `SimulatorTransport` | Tests, offline UI | Tunnel frames | Mimics 0x6B BL602 state machine + fault injection |
| `pixels/framebuffer.py` | `PixelFrameBuffer.set_pixel`, `fill`, `apply_gradient`, `snapshot` | `WreathController`, UI, `FrameScheduler` | RGB `(0..255)` + brightness `(0.0..1.0)` | Thread-safe scaled `PixelSlot` snapshot |
| `pixels/mapping.py` | `LogicalToPhysicalMapper.to_doodle_pixels`, `to_compact_groups` | `WreathController` | Logical `PixelSlot` sequence | Reordered `DoodlePixel` list (`E1 23`) or 20 `E1 22` records |
| `scheduler/engine.py` | `FrameScheduler.start`, `stop`, `_run_loop` | `WreathController` | `HostEffect`, `target_fps` (`1..18`) | Streams rendered frames at capped rate without blocking UI |
| `devices/wreath.py` | `WreathController` | Web server, CLIs, library users | High-level API calls | Dispatches commands, tracks state/capabilities, guards unsupported calls |
| `ui/server.py` | `LightingConsoleServer`, `create_app_handler` | `python3 -m controller web` | HTTP/JSON API calls | Controls `ControllerManager` and serves SPA |

---

## 4. Legacy Bugs Resolved During Refactoring

1. **Static `[G]` / `[B]` lookup bug** in `HLEffect.py` and `HLMasterEffects.py` (`COLOR_MAP.get(cmd, 0)` looked up `'G'` instead of `'GREEN'`, always sending Red).
2. **Gravity `[G]` vs Green `[G]` key collision** in `HLEffect.py`/`HLMasterEffects.py` (`G` was unreachable for static Green because `GRAVITY` matched earlier).
3. **Import-time blocking `input()` / `sys.exit(1)`** in `HLEffect.py` and `HLMasterEffects.py` preventing module imports or automated tests.
4. **Unsynchronized global `SEQ_NUM` and socket mutations** shared between `main()` and `animation_loop()`.
5. **Duplicated protocol boilerplate** copied across 5 standalone files, with socket descriptor leaks in `controllights.py`.
6. **Undocumented `requests` dependency** in `weather.py` and broken filename reference (`wreath_weather.py`) in `README.md`.
