"""Showcase cycling through all 7 3D-mapped physics & experimental wreath effects.

Usage:
    python3 examples/physics_3d_showcase.py [--ip 10.0.0.207] [--sim] [--seconds 8]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from controller.devices.wreath import WreathController
from controller.discovery.wifi_discovery import discover_wifi_devices
from controller.transports.simulator import SimulatorTransport

SHOWCASE_SEQUENCE = [
    ("firefly_3d", "3D Wandering Firefly (Hover-dart flight + luciferin glow)"),
    ("firefly_swarm_3d", "Moonlit Firefly Swarm (3 drifting fireflies across pine depth)"),
    ("candle_3d", "3D Pillar Candle (Sapphire wick + swaying 12:00 flame)"),
    ("convection_fire_3d", "Thermal Convection Fire (6:00 coals -> rising buoyant arcs)"),
    ("pendulum_wave_3d", "Gravity Pendulum & Elastic Shockwaves"),
    ("jacobs_ladder_3d", "Tesla Jacob's Ladder (6:00 electrodes -> climbing plasma arc -> 12:00 snap)"),
    ("ripple_pond_3d", "2D Raindrop Ripples (Euclidean concentric wavefronts)"),
    ("heartbeat_3d", "3D Living Heartbeat (LUB inner -> DUB arterial outer wave)"),
    ("dna_helix_3d", "3D Twisting DNA Helix (Front/back strands + golden inner rungs)"),
    ("quantum_interference_3d", "3D Quantum Wave Interference"),
    ("black_hole_3d", "Relativistic Black Hole (Keplerian inner speedup + Doppler beaming)"),
    ("bioluminescent_3d", "Bioluminescent 3D Reef & Firefly Mating Pulses"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="3D Physics & Experimental Wreath Showcase")
    parser.add_argument("--ip", help="Controller IP address")
    parser.add_argument("--sim", action="store_true")
    parser.add_argument("--seconds", type=float, default=8.0, help="Seconds per effect")
    parser.add_argument("--fps", type=float, default=12.0)
    args = parser.parse_args(argv)

    if args.sim:
        ctrl = WreathController(SimulatorTransport(), target_fps=args.fps)
    else:
        ip = args.ip
        if not ip:
            found = discover_wifi_devices(timeout=1.5, enrich_at_info=False)
            ip = found[0].ip if found else "10.0.0.207"
        ctrl = WreathController(ip, target_fps=args.fps)

    ctrl.connect()
    ctrl.power_on()
    try:
        for idx, (fx_id, desc) in enumerate(SHOWCASE_SEQUENCE, start=1):
            print(f"[{idx}/{len(SHOWCASE_SEQUENCE)}] {desc}")
            ctrl.set_effect(fx_id, speed=0.6, target_fps=args.fps)
            time.sleep(args.seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ctrl.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
