# Feature Verification Matrix (`FEATURE_MATRIX.md`)

Every row reflects verification status observed directly in tests and live hardware execution on `10.0.0.207` (`AK001-ZJ21413`, `0x6B`) and BLE `IOTWFC00`.

| Feature | Implemented | Unit-Tested | Simulator-Tested | Device-Tested | Status | Notes |
|---|---|---|---|---|---|---|
| UDP `48899` Discovery + AT Info (`AT+LVER`, `AT+SOCKB`, `AT+WMODE`) | Yes | Yes | N/A | Yes | **Working** | Discovered `10.0.0.207` (`B4:E8:42:A7:FC:00`) |
| BLE Discovery (`IOTWFC00` + `0x5A01` parser) | Yes | Yes | N/A | Yes | **Working** | Works on macOS via CoreBluetooth |
| Wi-Fi TCP `5577` Tunnel + Stream Framing + Reconnect | Yes | Yes | Yes | Yes | **Working** | Handles partial reads & checksum verification |
| BLE GATT `0xFFFF` (`FF01`/`FF02`) Queries & Color | Yes | Yes | N/A | Yes | **Working** | Verified `EA 81`, `0F 11`, `E1 22` over BLE |
| Power On / Power Off (`0x71 0x23/24 0x0F`) | Yes | Yes | Yes | Yes | **Working** | Verified via `EA 81` `[6]` (`0x23` / `0x24`) |
| Extended State Readback (`0x81 0x8A 8B` -> `EA 81`) | Yes | Yes | Yes | Yes | **Working** | 27-byte state parsed & exposed |
| RTC Time & Remote Config Query (`0x11`, `0x2B`) | Yes | Yes | Yes | Yes | **Working** | Verified checksums & timestamps |
| Solid Color & White Channel (`E1 22` / `E0 C1`) | Yes | Yes | Yes | Yes | **Working** | Verified HSV + `WB` updates |
| 20-Group Compact Color (`set_zones`) | Yes | Yes | Yes | Yes | **Working** | 20 independent zones via `E1 22` |
| 50-Pixel Individual Control (`set_pixel` + `show` / `E1 23`) | Yes | Yes | Yes | Yes | **Working** | Physically confirmed 50 independent LEDs |
| Logical-to-Physical Mapping (`origin`, `reverse`) | Yes | Yes | Yes | Yes | **Working** | Ring offset & CW/CCW direction |
| Master Brightness Scaling (`set_brightness`) | Yes | Yes | Yes | Yes | **Working** | Scales color, doodle pixels, and scheduler |
| Host Per-Pixel Effects Engine (38 effects incl. 3D Physics/Nature/Experimental) | Yes | Yes | Yes | Yes | **Working** | Live-streamed at 12–18.7 fps (`candle_3d`, `firefly_3d`, `ring_counter_spin`, etc.) |
| 3D Physical Wreath Map (`wreath_layout.py` + 3D Pixel Canvas) | Yes | Yes | Yes | Yes | **Working** | 44/50 LEDs physically mapped across `inner`/`front`/`outer`/`back` layers |
| Keyframe Timeline Editor & Playback (`cut` / `linear`) | Yes | Yes | Yes | Via `E1 23` | **Working** | Uses verified `E1 23` streaming pipeline |
| Controller-Native Scenes (`E1 21`) & Overlays (`E1 26`) | Yes | Yes | Yes | Yes | **Working** | Verified `mode=0x25` / `0x66` transitions |
| Optical Telegraphy (Morse WPM & Binary BPS) | Yes | Yes | Yes | Via `set_color` | **Working** | Non-blocking in Web UI & CLI |
| Open-Meteo Weather Sync | Yes | Yes | Yes | Via `set_color` | **Working** | Uses stdlib `urllib` |
| Web Lighting Console UI + Pixel Canvas + Dev Inspector | Yes | N/A | Yes | Yes | **Working** | Tested HTTP API & simulator + live backend |
| BLE 50-Pixel `E1 23` Streaming | Guarded | N/A | N/A | N/A | **Limited** | 367B exceeds 244B BLE `withoutResponse` MTU; raises `UnsupportedCapabilityError` |
| Streaming > 18 FPS over Wi-Fi TCP | Guarded | Yes | Yes | Yes | **Limited** | Hardware timed out at `20 ms` (`50 fps`); capped at `18 FPS` |
| Hardware Timers (`0x22`), Power Restore (`0x32`), Strip IC (`0x63`) | Guarded | N/A | Yes | Yes | **Unsupported** | Device returned `<none>`; raises `UnsupportedCapabilityError` |
| Music Mode (`0xE1 0x24` / `0xE1 0x07`) | Guarded | N/A | Yes | N/A | **Unsupported** | `E1 24` arm packet unverified; raises `UnsupportedCapabilityError` |
