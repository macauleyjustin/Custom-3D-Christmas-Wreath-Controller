"""Optical telegraphy CLI (Morse code & ASCII binary) using ``controller``."""

from __future__ import annotations

import argparse

from controllights import resolve_controller
from controller.effects.telegraphy import transmit_binary, transmit_morse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wreath Optical Telegraph (Morse / Binary)")
    parser.add_argument("--ip", help="Controller IP address (auto-discovers if omitted)")
    parser.add_argument("--sim", action="store_true", help="Use simulator transport")
    parser.add_argument("--mode", choices=("morse", "binary"), help="Transmission mode")
    parser.add_argument("--text", help="Message to transmit")
    parser.add_argument("--color", default="GREEN", help="Morse ON color")
    parser.add_argument("--one-color", default="BLUE", help="Binary '1' color")
    parser.add_argument("--zero-color", default="RED", help="Binary '0' color")
    parser.add_argument("--rate", type=float, help="WPM for morse or BPS for binary")
    parser.add_argument("--loop", action="store_true", help="Loop continuously until Ctrl+C")
    args = parser.parse_args(argv)

    ctrl = resolve_controller(ip=args.ip, sim=args.sim, interactive=(args.mode is None))
    try:
        if args.mode and args.text:
            if args.mode == "morse":
                transmit_morse(ctrl, args.text, color=args.color, wpm=args.rate or 15.0, loop=args.loop)
            else:
                transmit_binary(
                    ctrl,
                    args.text,
                    one_color=args.one_color,
                    zero_color=args.zero_color,
                    bps=args.rate or 2.0,
                    loop=args.loop,
                )
            return 0

        while True:
            print("\n--- WREATH TELEGRAPH ---")
            print("[1] Morse Code (Variable WPM)")
            print("[2] Binary Stream (Variable BPS)")
            print("[Q] Quit")
            mode = input("Select > ").strip().upper()
            if mode == "Q":
                break
            if mode == "1":
                txt = input("Message: ")
                col = input("Color [GREEN]: ").strip().upper() or "GREEN"
                wpm = float(input("Speed (1-50 WPM) [15]: ").strip() or 15)
                try:
                    transmit_morse(ctrl, txt, color=col, wpm=wpm, loop=True)
                except KeyboardInterrupt:
                    ctrl.set_color(0, 0, 0)
            elif mode == "2":
                txt = input("Message: ")
                c1 = input("Color for '1' [BLUE]: ").strip().upper() or "BLUE"
                c0 = input("Color for '0' [RED]: ").strip().upper() or "RED"
                bps = float(input("Speed (Bits Per Sec) [2]: ").strip() or 2)
                try:
                    transmit_binary(ctrl, txt, one_color=c1, zero_color=c0, bps=bps, loop=True)
                except KeyboardInterrupt:
                    ctrl.set_color(0, 0, 0)
    finally:
        ctrl.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
