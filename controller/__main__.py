"""Unified CLI & Web Lighting Console launcher (`python3 -m controller`)."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import webbrowser

from controller.devices.manager import ControllerManager
from controller.discovery.ble_discovery import discover_ble_devices
from controller.discovery.wifi_discovery import discover_wifi_devices
from controller.effects.library import list_host_effects
from controller.pixels.color import NAMED_COLORS
from controller.ui.server import LightingConsoleServer


def _connect_target(manager: ControllerManager, args: argparse.Namespace):
    if getattr(args, "sim", False):
        return manager.register_simulator()
    host = getattr(args, "ip", None)
    if not host:
        found = discover_wifi_devices(timeout=1.8, enrich_at_info=False)
        if found:
            host = found[0].ip
        else:
            print("No Wi-Fi wreath found via UDP 48899; falling back to simulator.", file=sys.stderr)
            return manager.register_simulator()
    return manager.add_wifi(host, port=getattr(args, "port", 5577), connect_now=True)


def cmd_discover(args: argparse.Namespace) -> int:
    wifi = discover_wifi_devices(timeout=args.timeout, enrich_at_info=True)
    ble = discover_ble_devices(timeout=args.timeout) if args.ble else []
    print(
        json.dumps(
            {
                "wifi": [d.__dict__ for d in wifi],
                "ble": [d.__dict__ for d in ble],
            },
            indent=2,
        )
    )
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    manager = ControllerManager()
    if args.sim:
        manager.register_simulator()
    elif args.ip:
        manager.add_wifi(args.ip, port=args.port, connect_now=True)
    else:
        found = discover_wifi_devices(timeout=1.5, enrich_at_info=True)
        if found:
            try:
                manager.add_wifi(found[0].ip, connect_now=True)
            except Exception:
                manager.register_simulator()
        else:
            manager.register_simulator()

    server = LightingConsoleServer(manager, host=args.bind, port=args.http_port)
    print(f"Holiday Bright Lights Lighting Console listening at {server.url}")
    if args.open_browser:
        webbrowser.open(server.url)

    stop_flag = False

    def _sig(_signum, _frame):
        nonlocal stop_flag
        stop_flag = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    server.start(background=True)
    try:
        while not stop_flag:
            time.sleep(0.3)
    finally:
        server.stop()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    manager = ControllerManager()
    ctrl = _connect_target(manager, args)
    try:
        print(json.dumps(ctrl.get_diagnostics(), indent=2))
    finally:
        manager.shutdown()
    return 0


def cmd_color(args: argparse.Namespace) -> int:
    manager = ControllerManager()
    ctrl = _connect_target(manager, args)
    try:
        ctrl.power_on()
        if args.name:
            rgb = NAMED_COLORS[args.name.upper()]
        else:
            rgb = (args.r, args.g, args.b)
        ctrl.set_brightness(args.brightness)
        ctrl.set_color(*rgb, white=args.white)
        print(f"Set color RGB{rgb} white={args.white} brightness={args.brightness:.2f} on {ctrl.transport.endpoint}")
    finally:
        manager.shutdown()
    return 0


def cmd_effect(args: argparse.Namespace) -> int:
    if args.list:
        for fx in list_host_effects():
            print(f"{fx.id:20s} [{fx.category}] - {fx.description}")
        return 0
    manager = ControllerManager()
    ctrl = _connect_target(manager, args)
    try:
        ctrl.power_on()
        ctrl.set_effect(args.name, speed=args.speed, target_fps=args.fps)
        print(f"Streaming {args.name} on {ctrl.transport.endpoint} (Ctrl+C to stop)...")
        end = time.monotonic() + args.duration if args.duration > 0 else None
        while end is None or time.monotonic() < end:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m controller",
        description="Holiday Bright Lights AK001-ZJ21413 (BL602) Controller Suite",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_disc = sub.add_parser("discover", help="Discover Wi-Fi and BLE controllers")
    p_disc.add_argument("--timeout", type=float, default=2.0)
    p_disc.add_argument("--ble", action="store_true")
    p_disc.set_defaults(func=cmd_discover)

    p_web = sub.add_parser("web", help="Launch the Web Lighting Console")
    p_web.add_argument("--ip", help="Controller IP address (auto-discovers if omitted)")
    p_web.add_argument("--port", type=int, default=5577)
    p_web.add_argument("--sim", action="store_true", help="Start in simulator mode")
    p_web.add_argument("--bind", default="127.0.0.1")
    p_web.add_argument("--http-port", type=int, default=8765)
    p_web.add_argument("--open-browser", action="store_true")
    p_web.set_defaults(func=cmd_web)

    p_stat = sub.add_parser("status", help="Connect and print device diagnostics")
    p_stat.add_argument("--ip")
    p_stat.add_argument("--port", type=int, default=5577)
    p_stat.add_argument("--sim", action="store_true")
    p_stat.set_defaults(func=cmd_status)

    p_col = sub.add_parser("color", help="Set solid RGB/named color")
    p_col.add_argument("--ip")
    p_col.add_argument("--port", type=int, default=5577)
    p_col.add_argument("--sim", action="store_true")
    p_col.add_argument("--name", choices=sorted(NAMED_COLORS))
    p_col.add_argument("--r", type=int, default=255)
    p_col.add_argument("--g", type=int, default=0)
    p_col.add_argument("--b", type=int, default=0)
    p_col.add_argument("--white", type=int, default=0)
    p_col.add_argument("--brightness", type=float, default=1.0)
    p_col.set_defaults(func=cmd_color)

    p_fx = sub.add_parser("effect", help="Stream a host per-pixel effect or native scene")
    p_fx.add_argument("name", nargs="?", default="rotating_rainbow")
    p_fx.add_argument("--list", action="store_true")
    p_fx.add_argument("--ip")
    p_fx.add_argument("--port", type=int, default=5577)
    p_fx.add_argument("--sim", action="store_true")
    p_fx.add_argument("--speed", type=float, default=0.5)
    p_fx.add_argument("--fps", type=float, default=12.0)
    p_fx.add_argument("--duration", type=float, default=0.0, help="Seconds to run (0=until Ctrl+C)")
    p_fx.set_defaults(func=cmd_effect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
