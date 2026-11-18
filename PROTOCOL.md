# Verified Communication Protocol Reference (`PROTOCOL.md`)

This specification documents only packet formats, headers, checksums, and field mappings **empirically verified** against live `AK001-ZJ21413` (`0x6B`, firmware `6B_30_20240524_ZG-BL-SBL-02`) hardware at `10.0.0.207` and BLE `IOTWFC00`.

---

## 1. UDP Discovery & Module Info (Port `48899`)

- **Discovery broadcast:** Send ASCII `HF-A11ASSISTHREAD` to `255.255.255.255:48899`.
  - **Observed reply:** `10.0.0.207,B4E842A7FC00,AK001-ZJ21413,6ed63336bc9a4c49b38792dbbd68fdbb` (`ip,MAC,model,device_token`)
- **Read-only AT queries (unicast UDP `48899`):**
  - `AT+LVER\r` → `+ok=6B_30_20240524_ZG-BL-SBL-02\r`
  - `AT+SOCKB\r` → `+ok=TCP,8815,sl8815us01.magichue.net\r`
  - `AT+WMODE\r` → `+ok=STA\r`

---

## 2. Wi-Fi TCP Framing (Port `5577`)

All TCP commands and responses use the 10-byte outer tunnel header plus a 1-byte checksum:

```text
Offset  Size  Field           Value / Meaning
0..3    4     Preamble        Fixed: B0 B1 B2 B3
4..5    2     Fixed Prefix    Fixed: 00 01
6       1     Version         0x02 (app/default) or 0x01 (both accepted)
7       1     Sequence        Rolling counter 0x00..0xFF (echoed in responses)
8..9    2     Inner Length    Big-endian uint16 length of <Inner Payload>
10..N   L     Inner Payload   Command or response payload (L bytes)
N+1     1     Checksum        sum(bytes[0..N+1]) & 0xFF
```

**Checksum Proof:** Because `0xB0 + 0xB1 + 0xB2 + 0xB3 = 710` and `710 % 256 = 198`, computing `(sum(bytes[4:-1]) + 198) % 256` (documented as `+198` or `-58 mod 256` in the original README) is mathematically identical to `sum(all_preceding_bytes) & 0xFF`.

---

## 3. Bluetooth Low Energy Framing (`IOTWFC00`)

- **Service Data UUID `0x5A01` (14 bytes):**
  `52 07 [B4 E8 42 A7 FC 00] [00 6B] [1E] [09] [01 02]`
  - `[2:8]`: MAC address (`B4:E8:42:A7:FC:00`)
  - `[8:10]`: Model ID (`0x006B` big-endian)
  - `[10]`: Build minor (`0x1E` = 30)
  - `[11]`: Subversion (`0x09` = 9)
- **GATT Service `0xFFFF`:**
  - Write Characteristic: `0xFF01` (`write`, `writeWithoutResponse`; MTU 512 / 244)
  - Notify Characteristic: `0xFF02` (`read`, `notify`; CCCD `0x2902`)
- **BLE v0 Transport Header (8 bytes prepended to inner payload):**

```text
[0x00] [seq] [0x80] [0x00] [len_hi] [len_lo] [len+1] [cmd_id: 0x0A=expect_resp | 0x0B=no_resp] [inner...]
```

- **BLE Notification Format (`FF02`):**
  8-byte header (`04 <seq> 80 00 ...`) followed by UTF-8 JSON:
  `{"code":0,"payload":"EA8101006B0923..."}`

---

## 4. Verified Inner Command & Response Table

| Command | Transport / Endpoint | Opcode | Payload Format | Device Response / Behavior | Constraints & Notes |
|---|---|---|---|---|---|
| **State Query** | TCP `5577` / BLE `FF01` | `81 8A 8B` (+ `96` on BLE) | 3B (TCP) or 4B with sum cs (BLE) | Returns 27B **`EA 81`** state inside tunnel / JSON | Always responds in `<50 ms` |
| **RTC Time Query** | TCP `5577` / BLE `FF01` | `11 1A 1B 0F` (+ `55` on BLE) | 4B / 5B | Returns 12B **`0F 11`** RTC timestamp | Validated checksum |
| **Remote Config Query** | TCP `5577` | `2B 2C 2D` | 3B | Returns 14B **`2B`** config packet | Validated checksum |
| **Power On** | TCP `5577` / BLE `FF01` | `71 23 0F` | 3B | No push ACK; `EA 81` `[6]` becomes `0x23` | Idempotent |
| **Power Off** | TCP `5577` / BLE `FF01` | `71 24 0F` | 3B | No push ACK; `EA 81` `[6]` becomes `0x24` | Idempotent |
| **Global HSV+W (`0xC1`)** | TCP `5577` | `E0 01 00 C1` | `E0 01 00 C1 [H] [S] [V] [WT] [WB] 00 00 0A 00 00` (14B) | Sets `EA 81` `mode=0x25, pat=0x66`, HSV & WT/WB | `H:0..180`, `S,V,WT,WB:0..100`; `0xA1`/`0xB1` ignored on `0x6B` |
| **Compact Color (20 Zones)** | TCP `5577` / BLE `FF01` | `E1 22` | `E1 22 00 00 00 00 14` + `20 x [H, S, V, 00, W]` (107B) | Sets `EA 81` `mode=0x24, pat=0x01` | Fits in single BLE `withoutResponse` write (`115B <= 244B`) |
| **Doodle Per-Pixel Frame** | TCP `5577` | `E1 23` | `E1 23 [f0..f3] [spd] [cnt_hi] [cnt_lo]` + `N x [anim, H, S, V, 00, 00, px_spd]` (359B for 50 LEDs) | Sets `EA 81` `mode=0x66, pat=0x01, spd=[spd]` | `anim`: `0x00` static, `0x08` pulse, `0x10` blink; `cnt=50` |
| **Frame Animation Overlay** | TCP `5577` | `E1 26` | `E1 26 [OO] [FF] 50 [spd] <45 x 00>` (51B) | Sets `EA 81` `mode=0x66, pat=OO+1, spd=[spd]` | Modifies dynamic motion of `E1 23` frame |
| **Native / Custom Scene** | TCP `5577` / BLE `FF01` | `E1 21` | `E1 21 [WW] 64 [MM] [OO] [FF] [PP] [SS] 00*6 [NN] <NN x 5B color>` | Sets `EA 81` `mode=0x25, pat=MM, spd=SS` | `MM`: scene program (`0x01`..`0x66`) |

---

## 5. `EA 81` Extended State Response Layout (27 Bytes)

Example captured from `10.0.0.207`:
`ea 81 01 00 6b 09 23 24 01 32 f0 3c 64 64 ff 00 0c 00 32 ff ff ff ff 01 00 00 03`

| Byte(s) | Sample | Field | Meaning |
|---|---|---|---|
| `0..1` | `EA 81` | Header | Extended state response signature |
| `2` | `01` | Version | State layout version |
| `3..4` | `00 6B` | Model ID | `0x006B` (107) |
| `5` | `09` | Subversion | Hardware/firmware sub-version (`9`) |
| `6` | `23` | Power | `0x23` = ON, `0x24` = OFF |
| `7` | `24` | Mode | `0x24` = Compact Color, `0x25` = Native/Custom Scene, `0x66` = Doodle Pixels |
| `8` | `01` | Pattern | Scene `MM` (when `mode=0x25`) or `OO+1` (when `mode=0x66`) |
| `9` | `32` | Speed | `0..100` (`50`) |
| `10` | `F0` | Flag | Observed `0xF0` |
| `11` | `3C` | Hue | `0..180` (`Hue/2`; Red `0` reads back as `180`) |
| `12` | `64` | Saturation | `0..100` (`100`) |
| `13` | `64` | Value | `0..100` (`100`) |
| `14` | `FF` | White Temp | `0..100` when active, `0xFF` (`255`) when RGB active |
| `15` | `00` | White Bright | `0..100` (`WB` / `C4`) |
| `16` | `0C` | Reserved/Cfg | Observed constant `0x0C` |
| `17..18` | `00 32` | LED Count | Big-endian uint16 (`50` pixels) |
| `19..26` | `FFFFFFFF01000003` | Tail | Observed constant trailer |
