"""Interactive terminal console backed by the verified ``controller`` library.

Replaces duplicated legacy logic in ``controllights.py``, ``HLEffect.py``, and
``HLMasterEffects.py`` while fixing the static color lookup bug, import-time I/O
blocking, and thread synchronization races. Original scripts remain preserved
under git tag ``original-baseline``.
"""

from __future__ import annotations

import argparse
import os
import sys

from controller.devices.wreath import WreathController
from controller.discovery.wifi_discovery import discover_wifi_devices
from controller.pixels.color import NAMED_COLORS
from controller.transports.simulator import SimulatorTransport

DEFAULT_IP = "192.168.12.101"


def resolve_controller(*, ip: str | None = None, sim: bool = False, interactive: bool = True) -> WreathController:
    """Resolve and connect a :class:`WreathController` via CLI arg, UDP discovery, or prompt."""
    if sim:
        ctrl = WreathController(SimulatorTransport())
        ctrl.connect()
        return ctrl

    target_ip = ip
    if not target_ip:
        discovered = discover_wifi_devices(timeout=1.5, enrich_at_info=False)
        if discovered:
            target_ip = discovered[0].ip
            print(f"Auto-discovered wreath at {target_ip} ({discovered[0].model})")
        elif interactive:
            entered = input(f"Enter Wreath IP Address (Enter for {DEFAULT_IP}): ").strip()
            target_ip = entered or DEFAULT_IP
        else:
            target_ip = DEFAULT_IP

    ctrl = WreathController(target_ip)
    ctrl.connect()
    return ctrl


def run_interactive_cli(ctrl: WreathController, *, title: str = "WREATH ANIMATION MASTER") -> None:
    """Run the interactive terminal controller menu."""
    current_status = "STATIC"
    ctrl.power_on()
    try:
        while True:
            if sys.stdout.isatty():
                os.system("cls" if os.name == "nt" else "clear")
            print(f"--- {title} ({ctrl.transport.endpoint}) ---")
            print(f"STATUS: {current_status} | LEDS: {ctrl.led_count}")
            print("---------------------------------------")
            print(" [1] Rainbow Swirl      [2] Fire Embers")
            print(" [3] Police Lightbar    [4] Thunderstorm")
            print(" [5] Festive Sparkle    [C] Candy Cane")
            print(" [H] Holly & Berry      [F] Frosty Shimmer")
            print(" [T] Thermal Flame      [V] Gravity Bounce")
            print(" [M] Comet Tail         [P] Plasma Nebula")
            print(" [W] Ocean Waves        [I] Starlight Twinkle")
            print(" [S] Dual Meteors       [N] Native Meteor (E1 21)")
            print("---------------------------------------")
            print(" [R] Red   [G] Green   [B] Blue   [Y] Yellow   [A] Aqua   [U] White")
            print(" [0] OFF / Stop Loop   [Q] Quit Program")

            cmd = input("Select Mode > ").strip().upper()
            if cmd == "Q":
                ctrl.power_off()
                break
            if cmd == "0":
                ctrl.power_off()
                current_status = "OFF"
            elif cmd == "1":
                ctrl.set_effect("rotating_rainbow")
                current_status = "RAINBOW"
            elif cmd == "2":
                ctrl.set_effect("fire")
                current_status = "FIRE"
            elif cmd == "3":
                ctrl.set_effect("police")
                current_status = "POLICE"
            elif cmd == "4":
                ctrl.set_effect("thunderstorm")
                current_status = "THUNDERSTORM"
            elif cmd == "5":
                ctrl.set_effect("sparkle")
                current_status = "SPARKLE"
            elif cmd == "C":
                ctrl.set_effect("candy_cane")
                current_status = "CANDY_CANE"
            elif cmd == "H":
                ctrl.set_effect("holly")
                current_status = "HOLLY"
            elif cmd == "F":
                ctrl.set_effect("frosty")
                current_status = "FROSTY"
            elif cmd == "T":
                ctrl.set_effect("thermal_flame")
                current_status = "THERMAL_FLAME"
            elif cmd == "V":
                ctrl.set_effect("gravity")
                current_status = "GRAVITY"
            elif cmd == "M":
                ctrl.set_effect("comet")
                current_status = "COMET"
            elif cmd == "P":
                ctrl.set_effect("plasma")
                current_status = "PLASMA"
            elif cmd == "W":
                ctrl.set_effect("waves")
                current_status = "WAVES"
            elif cmd == "I":
                ctrl.set_effect("twinkle")
                current_status = "TWINKLE"
            elif cmd == "S":
                ctrl.set_effect("meteor")
                current_status = "METEOR"
            elif cmd == "N":
                ctrl.set_effect("native:native_meteor")
                current_status = "NATIVE_METEOR"
            elif cmd in {"R", "G", "B", "Y", "A", "U"}:
                key_map = {
                    "R": "RED",
                    "G": "GREEN",
                    "B": "BLUE",
                    "Y": "YELLOW",
                    "A": "AQUA",
                    "U": "WHITE",
                }
                name = key_map[cmd]
                ctrl.power_on()
                ctrl.set_color(*NAMED_COLORS[name])
                current_status = f"STATIC ({name})"
    finally:
        ctrl.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Holiday Bright Lights Wreath CLI Controller")
    parser.add_argument("--ip", help="Controller IP address (auto-discovers if omitted)")
    parser.add_argument("--sim", action="store_true", help="Run against virtual device simulator")
    args = parser.parse_args(argv)
    ctrl = resolve_controller(ip=args.ip, sim=args.sim)
    run_interactive_cli(ctrl, title="HOLIDAY BRIGHT WREATH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
