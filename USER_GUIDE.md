# User Guide (`USER_GUIDE.md`)

## 1. Prerequisites & Installation

- **Python 3.10+** (standard library only; zero mandatory `pip` packages).
- Ensure your wreath controller is powered on and joined to the same local Wi-Fi network (for Wi-Fi control) or within Bluetooth range on macOS (for BLE queries/solid colors).

---

## 2. Launching the Web Lighting Console

Run the built-in web console (automatically scans UDP `48899` or falls back to the virtual simulator if offline):

```bash
python3 -m controller web --open-browser
```

Or specify a known IP or force Simulator mode:

```bash
python3 -m controller web --ip 10.0.0.207 --open-browser
python3 -m controller web --sim --open-browser
```

### Console Tabs
1. **Lighting & Device:**
   - **Scan Wi-Fi (UDP 48899)** or **Scan BLE**, then click **Connect** on your wreath.
   - Control **Power**, **Color Picker**, **White Channel (`WB`)**, **Master Brightness**, **38 Per-Pixel Host Effects** (including custom-wrapped `3D Physics`, `3D Nature`, `3D Experimental`, and `3D Wreath` spatial effects), **Native `E1 21` Scenes**, **Dynamic `E1 26` Overlays**, **Morse/Binary Telegraphy**, and **Weather Sync**.
   - Keep **Stream Rate** between `1–18 FPS` (default `12 FPS` is smooth and rock-solid on the BL602 Wi-Fi chip).
2. **Pixel Editor (50 LEDs):**
   - Toggle **3D Physical Map** to view and paint every bulb at its actual physical position on your custom-wrapped wreath (cyan border = `inner` ring, dashed border = `back` buried in branches), or uncheck to view raw index ring `0..49`.
   - Use **Paint Range** (with Start, End, Step), **Multi-Stop Gradient**, **Rotate +1/-1**, and **Logical-to-Physical Mapping** (`Origin 0..49` and `Counter-Clockwise`).
   - Save and reload custom patterns locally (`~/.holiday_bright_lights/patterns.json`).
3. **Animation Editor:**
   - Capture painted frames from the Pixel Editor onto a **Keyframe Timeline**, adjust per-frame **Duration (ms)** and **Transition (`Linear Fade` vs `Instant Cut`)**, toggle **Loop**, and play back or save timelines (`~/.holiday_bright_lights/timelines.json`).
4. **Developer Console:**
   - Clearly separated engineering panel displaying live TX/RX hexadecimal packets, RTT latency, parsed opcodes, raw inner payload injection (with explicit write-confirmation guard), and one-click JSON diagnostic export.

---

## 3. Command-Line Quick Reference

```bash
# Discover Wi-Fi & BLE controllers
python3 -m controller discover --ble

# Inspect live device state & diagnostics
python3 -m controller status --ip 10.0.0.207

# Set color
python3 -m controller color --ip 10.0.0.207 --name GREEN --brightness 0.8

# Stream a per-pixel effect
python3 -m controller effect rotating_rainbow --ip 10.0.0.207 --speed 0.6 --fps 12

# Interactive terminal menus (refactored legacy CLIs)
python3 controllights.py --ip 10.0.0.207
python3 datasender.py --ip 10.0.0.207 --mode morse --text "HELLO" --rate 15
python3 weather.py 48910 --ip 10.0.0.207 --effect --once
```

---

## 4. Troubleshooting

- **Can't find the wreath automatically?** Confirm your Mac and wreath are on the same Wi-Fi subnet (`255.255.255.255:48899` UDP broadcast enabled) and not isolated on a guest VLAN.
- **Effects appear sluggish above 15 FPS?** Lower **Stream Rate** to `10–12 FPS`; the BL602 TCP stack stalls above ~20 FPS for full 50-pixel (`370 B`) frames.
- **Want the original 2025 scripts?** Check out git tag `original-baseline` (`git show original-baseline:HLMasterEffects.py`).
