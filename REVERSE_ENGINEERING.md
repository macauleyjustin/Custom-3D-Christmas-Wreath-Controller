# Reverse Engineering Log & Evidence (`REVERSE_ENGINEERING.md`)

This document records the controlled experiments, byte comparisons, corrected misconceptions, and unresolved protocol questions gathered against the live Holiday Bright Lights wreath (`10.0.0.207` / `IOTWFC00`).

---

## 1. Corrections to Prior Repository Assumptions

| Prior Claim (`README.md` / `Reverse Engineering The Protocol.MD`) | Empirical Finding | Evidence |
|---|---|---|
| Outer checksum uses a magic `+198` (`-58 mod 256`) offset | It is standard `sum(all_bytes_from_B0_to_end) & 0xFF`. `sum(B0 B1 B2 B3) = 710 ≡ 198 (mod 256)`. | Verified across every TX and RX tunnel packet (`81 8A 8B` -> `0x62`, `EA 81` -> `0xAA`). |
| Payload length field includes a 1-byte inner checksum | On TCP `5577`, `length = len(inner_payload)` directly; inner commands work without an inner checksum. | `81 8A 8B` (`len=3`) and `E1 22` (`len=107`) accepted and reflected in `EA 81`. |
| BLE only handles initial Wi-Fi credential handoff | BLE (`IOTWFC00`, GATT `0xFFFF` `FF01`/`FF02`) remains active and accepts full Zengge v0 transport commands, returning JSON `EA 81` and `0F 11` payloads. | Live CoreBluetooth probe returned `{"code":0,"payload":"EA81..."}` and updated `EA 81` hue to `106` via `E1 22` over BLE. |
| Individual pixel control uses `0xE1 0x26` with ~80–100 bitmasked LEDs | `0xE1 0x23` transmits full 50-pixel (`0x0032`) HSV frames (7 bytes/pixel); `0xE1 0x26` selects dynamic frame animation overlays (`pat = OO + 1`). | `E1 23` switched `EA 81` to `mode=0x66`; `E1 26` with `OO=0x04` changed `pat` to `0x05`; physical 5-band pattern lit all 50 LEDs individually. |

---

## 2. Controlled Live Experiments & Byte Diffs

### Experiment A — State & Query Discovery (`10.0.0.207:5577`)
- `81 8A 8B` (both raw `818a8b96` and `B0`-wrapped) → returned 27-byte `EA 81 ... 03` (`mode`, `pat`, `spd`, `H`, `S`, `V`, `WT`, `WB`, `leds=50`).
- `11 1A 1B 0F` → returned `0f 11 14 1a 0b 12 0c 11 15 03 00 a0` (`2026-11-18T12:17:21`, weekday `3`, checksum `0xa0`).
- `2B 2C 2D` → returned `2b 03 00 01 00 00 3c 00 00 00 00 00 00 6b` (checksum `0x6b`).
- Non-responding queries (with and without inner checksum, `ver=0x01` & `ver=0x02`):
  - `22 2A 2B 0F` (timers) → `<none>`
  - `32 3A 3B 0F` (power restore) → `<none>`
  - `63 12 21 [0F|F0]` (strip IC config) → `<none>`
  - `72 00 72` (legacy music query) → `<none>`

### Experiment B — Power & Color Isolation (`EA 81` Diffs)
1. `71 24 0F` → `[6]` transitioned `0x23` → `0x24` (OFF). `71 23 0F` → `[6]` transitioned `0x24` → `0x23` (ON).
2. `E0 01 00 A1` and `E0 01 00 B1` (standard `flux_led` `0xB6` write modes) → **ignored** by `0x6B`; state stayed frozen until `0xC1` or `E1 22`.
3. `E0 01 00 C1`:
   - `(0, 100, 100)` → `mode=0x25 pat=0x66 H=180 S=100 V=100 WT=255 WB=0`
   - `(60, 100, 100)` → `mode=0x25 pat=0x66 H=60 S=100 V=100`
   - `(120, 100, 50)` → `mode=0x25 pat=0x66 H=120 S=100 V=49`
   - `(0, 0, 0, 50, 80)` → `mode=0x25 pat=0x66 H=0 S=0 V=0 WT=49 WB=79`
4. `E1 22 00 00 00 00 14` (20 × 5-byte records):
   - `[60, 50, 75, 0, 0]*20` → `mode=0x24 pat=0x01 H=60 S=49 V=74`
   - `[60, 100, 25, 0, 0]*20` → `mode=0x24 pat=0x01 H=60 S=100 V=25`
   - `[0, 0, 0, 0, 100]*20` → `mode=0x24 pat=0x01 H=0 S=0 V=0 WT=0 WB=100`

### Experiment C — Per-Pixel `E1 23` & Overlay `E1 26`
- Sending `E1 23 00 00 00 50 64 00 32` + 50 × 7B records (10 Red, 10 Green, 10 Blue, 10 Yellow, 10 White):
  - `EA 81` updated to `mode=0x66 pat=0x01 spd=100 leds=50`.
  - Physical observation confirmed all 5 distinct color bands lit simultaneously across the entire wreath in exact Red → Green → Blue → Yellow → White order.
- Sending `E1 26 [OO] 02 50 4B` + 45 × `0x00`:
  - `OO=0x00` → `pat=0x01, spd=75`
  - `OO=0x01` → `pat=0x02, spd=75`
  - `OO=0x04` → `pat=0x05, spd=75`
  - `OO=0x07` → `pat=0x08, spd=75`
  - `OO=0x10` → `pat=0x11, spd=75`
  - `OO=0x1E` → `pat=0x1F, spd=75`

### Experiment D — Sustained Streaming Benchmark (50-Pixel `E1 23` over Wi-Fi TCP)
- `150 ms` interval (`6.5 fps`, 25 frames): 0 errors, post-stream `EA 81` OK
- `100 ms` interval (`9.7 fps`, 35 frames): 0 errors, post-stream `EA 81` OK
- `66 ms` interval (`14.4 fps`, 45 frames): 0 errors, post-stream `EA 81` OK
- `50 ms` interval (`18.7 fps`, 50 frames): 0 errors, post-stream `EA 81` OK
- `20 ms` interval (40 frames): controller socket stalled and timed out on subsequent `EA 81` query.
- **Conclusion:** Safe production `FrameScheduler` cap set to `18.0 FPS` max, `12.0 FPS` default.

### Experiment E — BLE Transport Verification (`IOTWFC00`)
- Negotiated MTU: `512` (`withResponse`), `244` (`withoutResponse`).
- Sending raw `B0 B1 B2 B3...` to `FF01` yielded `08 00 80 00 00 00 00` error response.
- Wrapping in BLE v0 header (`00 <seq> 80 00 <len2> <len+1> 0A/0B`) yielded live JSON responses:
  - `81 8A 8B 96` → `{"code":0,"payload":"EA81..."}`
  - `11 1A 1B 0F 55` → `{"code":0,"payload":"0F11..."}`
  - `E1 22` (Blue 100% / RGB `(0, 120, 255)`) → reflected in `EA 81` (`H=106, S=100, V=100`) after ~180–250 ms propagation.

---

## 3. Unresolved / Intentionally Guarded Areas

1. **Music Mode (`0xE1 0x24` arm packet & `0xE1 0x07` stream):** Full `E1 24` payload format is not captured/verified on `0x6B`; `WreathController.set_music_level()` raises `UnsupportedCapabilityError`.
2. **BLE Multi-Segment Fragmentation:** Sending a 367-byte 50-pixel `E1 23` frame exceeds the 244-byte `withoutResponse` MTU; segmented BLE transport (`flags & 0x40`) was not captured/verified, so `BLETransport` enforces MTU bounds and recommends Wi-Fi TCP for full-frame pixel streaming.
3. **Timers (`0x22`), Power-Restore (`0x32`), Strip IC Reconfiguration (`0x63`):** Returned no response on `0x6B`; guarded with `UnsupportedCapabilityError`.
4. **Hardware-Level Electrical Wire Protocol:** Sealed controller enclosure prevents logic-analyzer probing of the LED data pin; pixel count (`50`) and color ordering are verified through `EA 81` and physical strand observation.
