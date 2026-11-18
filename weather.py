"""Open-Meteo weather wreath synchronization CLI."""

from __future__ import annotations

import argparse
import time
from datetime import datetime

from controllights import resolve_controller
from controller.effects.weather_sync import (
    apply_weather_to_controller,
    fetch_current_weather_code,
    fetch_lat_lon,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated Weather Wreath")
    parser.add_argument("location", nargs="?", help="Zip code or city name (e.g. 48910)")
    parser.add_argument("--ip", help="Controller IP address (auto-discovers if omitted)")
    parser.add_argument("--sim", action="store_true", help="Use simulator transport")
    parser.add_argument("--interval", type=int, default=3600, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Update weather once and exit")
    parser.add_argument("--effect", action="store_true", help="Use animated per-pixel weather effect")
    args = parser.parse_args(argv)

    loc_query = args.location or input("Enter your Zip Code or City (e.g., 48910): ").strip() or "48910"
    geo = fetch_lat_lon(loc_query)
    if geo is None:
        lat, lon, name = 42.7325, -84.5555, "Lansing"
        print("Could not geocode location; using default (Lansing, MI).")
    else:
        lat, lon, name = geo

    ctrl = resolve_controller(ip=args.ip, sim=args.sim, interactive=False)
    print(f"Tracking weather for {name} ({lat}, {lon}) on {ctrl.transport.endpoint}")
    try:
        while True:
            stamp = datetime.now().strftime("%H:%M:%S")
            code = fetch_current_weather_code(lat, lon)
            app = apply_weather_to_controller(ctrl, code, use_per_pixel_effect=args.effect)
            print(f"[{stamp}] WMO {code} ({app.label}) -> RGB{app.rgb}")
            if args.once:
                break
            time.sleep(max(10, args.interval))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ctrl.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
