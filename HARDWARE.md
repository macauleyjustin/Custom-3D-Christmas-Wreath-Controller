# Controller Hardware & Physical Strand Identification (`HARDWARE.md`)

All hardware findings below were gathered from live probing of the controller (`10.0.0.207` / BLE `IOTWFC00`), physical strand visual verification, and cross-referencing the official [`bouffalolab/bouffalo_sdk`](https://github.com/bouffalolab/bouffalo_sdk) repository.

---

## 1. Microcontroller & Wireless Module

| Attribute | Confirmed Value | Evidence Source |
|---|---|---|
| **Product / Model String** | `AK001-ZJ21413` | UDP `48899` (`HF-A11ASSISTHREAD`) reply |
| **MAC Address / OUI** | `B4:E8:42:A7:FC:00` (`B4:E8:42` = Bouffalo Lab Limited) | UDP `48899` & BLE `0x5A01` service data |
| **SoC Family** | **Bouffalo Lab BL602** (32-bit RISC-V) | OUI + `ZG-BL-*` firmware family + `flux_led` `AK001-ZJ21413` hardware DB (`LEDENETChip.BL602`) |
| **CPU & Clock** | 32-bit RISC-V (`RV32IMFC`), PLL up to 192 MHz (per `bouffalo_sdk/bsp/board/bl602dk/board.c`) | `bouffalo_sdk` (`drivers/soc/bl602`, `bl602dk`) |
| **Memory (BL602 Datasheet / SDK)** | 276 KB SRAM (OCRAM + WRAM), 128 KB ROM, 32 KB L1 cache, 1 Kb eFuse, external/embedded QSPI XIP Flash with OTFAD AES support | `bouffalolab/bouffalo_sdk` |
| **Wireless Capabilities** | Wi-Fi 4 (`802.11 b/g/n` STA/SoftAP) + Bluetooth 5.0 Low Energy (BLE) | `bouffalo_sdk` + live concurrent Wi-Fi STA + BLE GATT activity |
| **Peripherals on BL602** | GPIO, SPI0, PWM v1, UART0/1, I2C0, I2S, IR, ADC/DAC, DMA0, RTC, WDG, Hardware AES/SHA/TRNG | `bouffalolab/bouffalo_sdk/README.md` & `bl602dk/board.c` |

---

## 2. Firmware Identification & Operating State

| Field | Observed Value | Source |
|---|---|---|
| **Firmware Version String** | `6B_30_20240524_ZG-BL-SBL-02` | UDP `48899` `AT+LVER\r` |
| **Model Byte (`EA 81` [3:5])** | `0x006B` (decimal `107`) | TCP `5577` `EA 81` & BLE `0x5A01` |
| **Protocol / HW Subversion** | `0x09` (`9`), Build Minor `0x1E` (`30`) | `EA 81` [5] & BLE `0x5A01` [10..11] |
| **Build Date** | `2024-05-24` | `AT+LVER\r` (`20240524`) |
| **Wi-Fi Mode** | `STA` | UDP `48899` `AT+WMODE\r` |
| **Cloud Provisioning Server** | `TCP,8815,sl8815us01.magichue.net` | UDP `48899` `AT+SOCKB\r` |
| **BLE Local Name** | `IOTWFC00` | CoreBluetooth scan |
| **Firmware Origin** | **Original manufacturer firmware** (Zengge / Surplife `ZG-BL-SBL-02`) | Exact match with Zengge/Surplife ecosystem & `sl8815us01.magichue.net` |

### Bootloader, Debug & Recovery Notes
- Per `bouffalo_sdk`, BL602 boots from internal 128 KB BootROM over UART0 (`GPIO16` TX / `GPIO7` RX on `bl602dk`) when strap/boot pins select UART ISP flash mode, or executes from XIP QSPI Flash (`0x23000000` range).
- **No firmware flashing was attempted or performed.** The stock firmware already exposes full local Wi-Fi TCP (`5577`) and BLE (`0xFFFF`) control, including 50-pixel individual addressing (`0xE1 0x23`). Any future custom firmware (e.g., ESPHome / OpenBeken / custom `bouffalo_sdk` build) would require physical teardown to expose UART0/BOOT pins and first dumping the original QSPI flash image via `bflb-iot-tool` / `blflash` as a recovery backup before erasing flash.

---

## 3. Physical LED Strand Characterization

| Parameter | Verified Finding | Evidence |
|---|---|---|
| **Addressability** | **50 individually addressable RGB/HSV pixels** | `EA 81` bytes `[17:19]` = `0x0032` (`50`), confirmed physically via 5-band `E1 23` test (0–9 Red, 10–19 Green, 20–29 Blue, 30–39 Yellow, 40–49 White) lighting the entire wreath |
| **Physical vs Logical LED Count** | `50` logical pixels = `50` physical LEDs custom-wrapped around a 3D pine wreath (`44` mapped in `wreath_layout.py`: `2, 7–49`; `6` interpolated: `0, 1, 3–6`) | Visual verification & individual LED mapping on live custom wreath |
| **3D Depth & Clock Topology** | Strand weaves non-linearly across 4 radial/depth layers (`inner` r=0.56, `front` r=0.78, `outer` r=1.00, `back` buried in branches r=0.82) clockwise (`12:00`→`3:00`→`6:00`→`9:00`) | Direct per-bulb inspection (`2, 7–49`) via Pixel Editor |
| **Color Model on Wire** | Native **HSV** (`H: 0..180` = `0..360°`, `S: 0..100`, `V: 0..100`) + optional white level (`0..100`) | Confirmed via `E0 C1`, `E1 22`, `E1 23`, and `EA 81` readback |
| **Color Component Accuracy** | `H=0` Red, `H=60` Green, `H=120` Blue, `H=30` Yellow, `S=0` White | Visually confirmed in order on the physical wreath |
| **Grouping Behavior** | `E1 22` splits the strand into `20` logical color groups; `E1 23` addresses all `50` pixels individually | `E1 22` (20 records) vs `E1 23` (50 records) |
| **White Support** | Desaturated RGB white (`S=0, V=100`) and white-channel byte (`C4` / `WB` `0..100`, `WT` `0..100` in `E0 C1`) | `EA 81` bytes `[14..15]` (`WT`, `WB`) updated on `E0 C1` and `E1 22` |
| **Animation Execution** | Supports **both** host-streamed per-pixel frames (`E1 23`) and controller-native scenes (`E1 21`) / overlays (`E1 26`) | Verified via `EA 81` mode transitions (`0x66`, `0x25`, `0x24`) |
| **Verified Frame Rate Limits** | Sustained 50-pixel TCP streaming healthy at **6.5 – 18.7 fps** (`150 ms` to `50 ms`); **stalled/timed out at 20 ms (`50 fps`)** | Sustained streaming benchmark against `10.0.0.207` |
| **BLE Payload / MTU Constraint** | BLE GATT `writeWithoutResponse` MTU is **244 bytes**, `writeWithResponse` MTU is **512 bytes**. A 50-pixel `E1 23` frame is `367 bytes` wired. | CoreBluetooth negotiated MTU readout on `IOTWFC00` |
| **Electrical LED Protocol** | Not directly observable without opening the sealed controller housing (SPI/PWM/GPIO single-wire WS281x-style or clocked pixel IC driven by BL602). `0x63` IC config query is unsupported on `0x6B` firmware. | Sealed hardware + non-response to `0x63 0x12 0x21` |
