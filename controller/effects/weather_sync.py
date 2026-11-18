"""Open-Meteo weather lookup and wreath color/effect mapping (stdlib urllib)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

from controller.pixels.color import RGB

if TYPE_CHECKING:
    from controller.devices.wreath import WreathController

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class WeatherAppearance:
    """Mapped visual presentation for a WMO weather code."""

    wmo_code: int
    label: str
    rgb: RGB
    recommended_effect: str | None = None


def map_wmo_weather(code: int) -> WeatherAppearance:
    """Map a WMO weather code to a color and optional per-pixel effect."""
    if code == 0:
        return WeatherAppearance(code, "Clear Sky", (255, 190, 0), None)
    if code in (1, 2, 3):
        return WeatherAppearance(code, "Cloudy", (130, 130, 140), "waves")
    if code in (45, 48):
        return WeatherAppearance(code, "Fog", (0, 130, 130), "frosty")
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return WeatherAppearance(code, "Rain", (0, 70, 255), "waves")
    if code in (71, 73, 75, 77, 85, 86):
        return WeatherAppearance(code, "Snow", (235, 245, 255), "snowfall")
    if code in (95, 96, 99):
        return WeatherAppearance(code, "Thunderstorm", (170, 0, 255), "thunderstorm")
    return WeatherAppearance(code, f"Weather ({code})", (0, 220, 80), None)


def fetch_lat_lon(query: str, timeout: float = 5.0) -> tuple[float, float, str] | None:
    """Query Open-Meteo geocoding API for a zip code or city name."""
    url = f"{GEO_URL}?{urllib.parse.urlencode({'name': query, 'count': 1, 'language': 'en', 'format': 'json'})}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = data.get("results") or []
    if not results:
        return None
    top = results[0]
    return float(top["latitude"]), float(top["longitude"]), str(top.get("name", query))


def fetch_current_weather_code(lat: float, lon: float, timeout: float = 5.0) -> int:
    """Query Open-Meteo forecast API for current WMO weather code."""
    params = urllib.parse.urlencode(
        {"latitude": lat, "longitude": lon, "current": "weather_code", "timezone": "auto"}
    )
    url = f"{WEATHER_URL}?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return int(data["current"]["weather_code"])


def apply_weather_to_controller(
    ctrl: "WreathController",
    code: int,
    *,
    use_per_pixel_effect: bool = False,
) -> WeatherAppearance:
    """Apply WMO weather appearance to ``ctrl``."""
    appearance = map_wmo_weather(code)
    ctrl.power_on()
    if use_per_pixel_effect and appearance.recommended_effect:
        ctrl.set_effect(appearance.recommended_effect, speed=0.45)
    else:
        ctrl.stop_effect()
        ctrl.set_color(*appearance.rgb)
    return appearance
