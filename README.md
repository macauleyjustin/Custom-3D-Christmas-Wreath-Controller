# Custom 3D Christmas Wreath Controller (`AK001-ZJ21413` / Bouffalo Lab BL602)

> **Project Purpose & Scope:**  
> This application is the **completed end-state controller software** for a **custom-wrapped, custom-built 50-LED smart Christmas wreath** powered by a **Holiday Bright Lights "Brilliant" Series (`AK001-ZJ21413`)** controller (Bouffalo Lab `BL602` RISC-V SoC, Zengge/Surplife firmware `6B_30_20240524_ZG-BL-SBL-02`).  
> It supersedes the initial 2025 proof-of-concept scripts (preserved at git tag `original-baseline`) with a complete protocol stack, 3D physical wreath topology model, physics-driven lighting engine, Web Lighting Console, hardware simulator, and automated test suite.

---

## Why This Exists (Custom-Wrapped 3D Wreath Mapping)

When a 50-LED addressable strand is hand-wrapped around a 3D pine wreath rather than laid out in a flat circle, sequential pixel indices (`0..49`) jump across **depth layers** and loop back and forth through branches:

- **`inner` ring (`r ≈ 0.56`):** Inner perimeter halo facing the center opening
- **`front` / `outer` crown (`r ≈ 0.78–1.00`):** Foreground and outer-edge hero bulbs
- **`back` buried layer (`r ≈ 0.82`, recessed):** Bulbs tucked inside/behind pine needles, ideal for glowing ambient foliage backlight rather than sharp foreground patterns

This project models **44 physically mapped LEDs (`2, 7–49`)** (with `0, 1, 3–6` smoothly interpolated) into true `(clock_hour, angle_deg, radius, x, y, depth_layer)` coordinates inside [controller/pixels/wreath_layout.py](controller/pixels/wreath_layout.py). Every 3D effect—from the swaying **3D Pillar Candle** and **Thermal Convection Fire** to the **3D Wandering Firefly**, **Tesla Jacob's Ladder**, **Quantum Wave Interference**, **Relativistic Black Hole**, and **3D Living Heartbeat**—renders directly in physical 3D wreath space.

*(If you build another custom-wrapped wreath, update `_OBSERVED_NODES` in [controller/pixels/wreath_layout.py](controller/pixels/wreath_layout.py) using the Pixel Editor's single-LED click tool.)*

---

## Key Capabilities & Technical Specs

| Subsystem | Confirmed Capability |
|---|---|
| **SoC & Firmware** | Bouffalo Lab **BL602** (`32-bit RISC-V`, Wi-Fi 4 + BLE 5.0, MAC OUI `B4:E8:42`), model `0x006B` (`AK001-ZJ21413`), firmware `6B_30_20240524_ZG-BL-SBL-02` |
| **Addressable Pixels** | **50 individual HSV pixels** (`0x0032` in `EA 81` state) via `0xE1 0x23` (`7 bytes/pixel`: `anim, H/2, S, V, 00, 00, px_speed`) |
| **Wi-Fi Control (`TCP 5577` + `UDP 48899`)** | Auto-discovery (`HF-A11ASSISTHREAD`), read-only AT info (`AT+LVER`, `AT+SOCKB`, `AT+WMODE`), `B0 B1 B2 B3` tunnel framing, sustained `E1 23` streaming up to `18.7 fps` (`12 FPS` default, `18 FPS` hard cap) |
| **BLE Control (`IOTWFC00`, GATT `0xFFFF`)** | Zengge BLE v0 framing over `FF01`/`FF02` with JSON payload decoding (`EA 81`, `0F 11`, `E1 22` compact color); `E1 23` streaming guarded due to `244 B` `withoutResponse` MTU |
| **Color & Zones** | `0xE1 0x22` 20-group compact color + white brightness (`WB`), plus legacy `0xE0 0x01 0x00 0xC1` global HSV+W |
| **Hardware-Native Scenes** | `0xE1 0x21` built-in scenes (`mode=0x25`) & `0xE1 0x26` dynamic frame overlays (`mode=0x66`) |
| **Lighting Engine** | **38 host per-pixel effects** (`3D Physics`, `3D Nature`, `3D Experimental`, `3D Wreath`, `Spectrum`, `Holiday`, `Weather`) + user-authored Keyframe Timelines (`cut`/`linear` interpolation) |
| **Web Lighting Console** | Pure-stdlib local web app (`http://127.0.0.1:8765`) featuring Device Diagnostics, **3D Physical Wreath Pixel Editor**, Keyframe Animation Editor, Telegraphy, Weather Sync, and Developer Hex Console |
| **Simulator & Tests** | Fault-injectable `SimulatedWreathDevice` + `19` automated unit/simulator/API/hardware tests |

---

## Quick Start (Zero Mandatory External Dependencies)

Requires **Python 3.10+** standard library only:

```bash
# 1. Launch the Web Lighting Console (auto-discovers wreath via UDP 48899, or uses simulator)
python3 -m controller web --open-browser

# 2. Or connect directly to a known wreath IP
python3 -m controller web --ip 10.0.0.207 --open-browser

# 3. Run the 3D physics & experimental showcase (cycles 12 custom 3D effects)
python3 examples/physics_3d_showcase.py --ip 10.0.0.207

# 4. Run the Fireplace -> Color Swirl -> Cosmic Aurora choreographed show
python3 examples/fireplace_swirl_show.py --ip 10.0.0.207

# 5. Run the automated test suite (unit, simulator, Web API, and live hardware if reachable)
python3 -m unittest discover -s controller/tests -v
```

---

## How It Works (Reverse Engineering Summary)

1. **Tunnel Checksum Breakthrough:** Early reverse engineering observed a `+198` (`-58 mod 256`) checksum offset. In reality, `0xB0 + 0xB1 + 0xB2 + 0xB3 = 710 ≡ 198 (mod 256)`, so the outer checksum is simply `sum(all_preceding_bytes) & 0xFF`.
2. **Per-Pixel Protocol Discovery:** `0xE1 0x26` sets frame animation overlays (`pat = OO + 1` in `EA 81`), while **`0xE1 0x23`** sends full 50-pixel HSV frames (`359 B` inner payload).
3. **BLE Dual-Transport Discovery:** Contrary to the initial assumption that BLE was provisioning-only, `IOTWFC00` accepts Zengge BLE v0 packets on `0xFFFF`/`FF01` and returns JSON-wrapped hex state payloads on `FF02`.
4. **3D Physical Wreath Calibration:** Stepping through individual LEDs in the Pixel Editor mapped the exact clock positions (`12:00` top, `3:00` right, `6:00` bottom, `9:00` left) and depth layers (`inner`, `front`, `outer`, `back`) of the custom-wrapped wreath.

---

## Complete Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Directory inventory, call chains, module responsibilities, and legacy bug fixes
- [HARDWARE.md](HARDWARE.md) — BL602 SoC specs, firmware identity, and custom-wrapped 3D 50-LED physical topology
- [PROTOCOL.md](PROTOCOL.md) — Verified UDP/TCP/BLE framing, `EA 81` state layout, and command specifications
- [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md) — Controlled experiments, packet diffs, streaming benchmarks, and resolved misconceptions
- [FEATURE_MATRIX.md](FEATURE_MATRIX.md) — Verification matrix across unit, simulator, and live hardware tests
- [USER_GUIDE.md](USER_GUIDE.md) — Everyday Web Console, Pixel Editor, Timeline Editor, and CLI instructions
- [DEVELOPER_API.md](DEVELOPER_API.md) — Reusable `controller` Python API reference
