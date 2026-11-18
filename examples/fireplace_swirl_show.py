"""Choreographed 3-stage wreath light show: 2D Fireplace -> Multi-Color Swirl -> Cosmic Aurora.

Calibrated to the physical wreath geometry reported by the user:
  - Index ~0:   Right (~3:30)
  - Index ~11:  Bottom hearth center (~6:00)
  - Index ~24:  Left (~9:00)
  - Index ~36:  Top center (~12:00)

Usage:
    python3 examples/fireplace_swirl_show.py [--ip 10.0.0.207] [--sim]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow direct execution from repo root or examples/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.devices.wreath import WreathController
from controller.discovery.wifi_discovery import discover_wifi_devices
from controller.effects.library import ColorSwirlEffect, CosmicAuroraEffect, Fireplace2DEffect
from controller.pixels.color import RGB, interpolate_rgb
from controller.transports.simulator import SimulatorTransport


def _resolve(ip: str | None, sim: bool) -> WreathController:
    if sim:
        ctrl = WreathController(SimulatorTransport())
        ctrl.connect()
        return ctrl
    target = ip
    if not target:
        found = discover_wifi_devices(timeout=1.5, enrich_at_info=False)
        target = found[0].ip if found else "10.0.0.207"
    ctrl = WreathController(target)
    ctrl.connect()
    return ctrl


def _push(ctrl: WreathController, pixels: list[RGB]) -> None:
    ctrl.framebuffer.set_all_rgb(pixels)
    ctrl._flush_framebuffer(frame_speed=100)


def run_show(
    ctrl: WreathController,
    *,
    fire_s: float = 12.0,
    swirl_s: float = 12.0,
    aurora_s: float = 14.0,
    fade_s: float = 2.0,
    fps: float = 14.0,
    bottom_index: int = 11,
) -> None:
    n = ctrl.led_count
    period = 1.0 / fps
    fire_fx = Fireplace2DEffect(speed=0.65, bottom_index=bottom_index)
    swirl_fx = ColorSwirlEffect(speed=0.68)
    aurora_fx = CosmicAuroraEffect(speed=0.62)

    ctrl.power_on()
    ctrl.set_brightness(1.0)

    def stream_stage(label: str, fx, duration_s: float, t_offset: float = 0.0) -> list[RGB]:
        print(f"Stage: {label} ({duration_s:.1f}s @ {fps:.0f} FPS)")
        t0 = time.monotonic()
        idx = 0
        last_px: list[RGB] = [(0, 0, 0)] * n
        while True:
            now = time.monotonic()
            elapsed = now - t0
            if elapsed >= duration_s:
                break
            last_px = fx.render(n, elapsed + t_offset, idx)
            _push(ctrl, last_px)
            idx += 1
            rem = period - (time.monotonic() - now)
            if rem > 0:
                time.sleep(rem)
        return last_px

    def crossfade(label: str, fx_from, fx_to, duration_s: float, offset_from: float) -> None:
        print(f"Transition: {label} ({duration_s:.1f}s)")
        t0 = time.monotonic()
        idx = 0
        while True:
            now = time.monotonic()
            elapsed = now - t0
            if elapsed >= duration_s:
                break
            alpha = elapsed / duration_s
            p1 = fx_from.render(n, offset_from + elapsed, idx)
            p2 = fx_to.render(n, elapsed, idx)
            blended = [interpolate_rgb(a, b, alpha) for a, b in zip(p1, p2)]
            _push(ctrl, blended)
            idx += 1
            rem = period - (time.monotonic() - now)
            if rem > 0:
                time.sleep(rem)

    stream_stage("1/3 2D Fireplace Hearth", fire_fx, fire_s)
    crossfade("Fireplace -> Color Swirl", fire_fx, swirl_fx, fade_s, fire_s)
    stream_stage("2/3 Multi-Color Wreath Swirl", swirl_fx, swirl_s, t_offset=fade_s)
    crossfade("Color Swirl -> Cosmic Aurora & Comets", swirl_fx, aurora_fx, fade_s, fade_s + swirl_s)
    final_px = stream_stage("3/3 Cosmic Aurora & Counter-Orbiting Comets", aurora_fx, aurora_s, t_offset=fade_s)

    # Hand off to hardware-native E1 26 flowing overlay so the wreath continues glowing after exit
    _push(ctrl, final_px)
    ctrl.set_doodle_overlay("flowing", speed_pct=70)
    print("Show complete! Handed off to hardware E1 26 flowing overlay.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choreographed 3-stage Fireplace -> Swirl -> Aurora show")
    parser.add_argument("--ip", help="Controller IP address")
    parser.add_argument("--sim", action="store_true", help="Run against simulator")
    parser.add_argument("--fire-s", type=float, default=12.0)
    parser.add_argument("--swirl-s", type=float, default=12.0)
    parser.add_argument("--aurora-s", type=float, default=14.0)
    parser.add_argument("--fade-s", type=float, default=2.0)
    parser.add_argument("--fps", type=float, default=14.0)
    parser.add_argument("--bottom-index", type=int, default=11)
    args = parser.parse_args(argv)

    ctrl = _resolve(args.ip, args.sim)
    try:
        run_show(
            ctrl,
            fire_s=args.fire_s,
            swirl_s=args.swirl_s,
            aurora_s=args.aurora_s,
            fade_s=args.fade_s,
            fps=args.fps,
            bottom_index=args.bottom_index,
        )
    finally:
        ctrl.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
