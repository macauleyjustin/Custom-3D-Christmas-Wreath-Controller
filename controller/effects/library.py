"""Rich per-pixel host effects engine (Phase 6)."""

from __future__ import annotations

import colorsys
import math
import random
from typing import Any

from controller.effects.base import EffectInfo, HostEffect, TimelineAnimation
from controller.exceptions import ValidationError
from controller.pixels.color import RGB, interpolate_rgb, scale_rgb
from controller.pixels.wreath_layout import build_wreath_layout


def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (round(r * 255), round(g * 255), round(b * 255))


class RainbowEffect(HostEffect):
    info = EffectInfo("rainbow", "Rainbow Gradient", "Spectrum", "Static or slow-drifting full rainbow across all LEDs", 0.3)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        shift = elapsed_s * (0.05 + self.speed * 0.45)
        return [_hsv(i / count + shift) for i in range(count)]


class RotatingRainbowEffect(HostEffect):
    info = EffectInfo("rotating_rainbow", "Rotating Rainbow", "Spectrum", "Smooth rotating spectrum wheel around the wreath", 0.5)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        shift = elapsed_s * (0.15 + self.speed * 1.4)
        return [_hsv(i / count - shift) for i in range(count)]


class ColorChaseEffect(HostEffect):
    info = EffectInfo("color_chase", "Color Chase", "Motion", "Segmented color blocks chasing around the wreath", 0.55)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        c1: RGB = tuple(self.params.get("primary", (255, 40, 0)))  # type: ignore[assignment]
        c2: RGB = tuple(self.params.get("secondary", (0, 120, 255)))  # type: ignore[assignment]
        pos = elapsed_s * (4.0 + self.speed * 26.0)
        out: list[RGB] = []
        for i in range(count):
            phase = ((i - pos) % 10.0) / 10.0
            if phase < 0.4:
                out.append(c1)
            elif phase < 0.5:
                out.append(interpolate_rgb(c1, c2, (phase - 0.4) / 0.1))
            elif phase < 0.9:
                out.append(c2)
            else:
                out.append(interpolate_rgb(c2, c1, (phase - 0.9) / 0.1))
        return out


class CometEffect(HostEffect):
    info = EffectInfo("comet", "Comet Tail", "Motion", "Bright orbiting comet with smoothly decaying tail", 0.6)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        color: RGB = tuple(self.params.get("color", (0, 210, 255)))  # type: ignore[assignment]
        head = (elapsed_s * (5.0 + self.speed * 30.0)) % count
        tail_len = max(4, count // 4)
        out: list[RGB] = []
        for i in range(count):
            dist = (head - i) % count
            if dist < tail_len:
                fade = (1.0 - dist / tail_len) ** 2.2
                out.append(scale_rgb(color, fade))
            else:
                out.append((0, 0, 0))
        return out


class MeteorEffect(HostEffect):
    info = EffectInfo("meteor", "Dual Meteors", "Motion", "Two counter-phased glowing meteors with warm sparks", 0.6)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        h1 = (elapsed_s * (6.0 + self.speed * 28.0)) % count
        h2 = (h1 + count / 2.0) % count
        tail_len = max(5, count // 5)
        out: list[RGB] = []
        for i in range(count):
            d1 = (h1 - i) % count
            d2 = (h2 - i) % count
            if d1 < 1.2:
                c = (255, 255, 230)
            elif d1 < tail_len:
                c = scale_rgb((255, 90, 20), (1.0 - d1 / tail_len) ** 1.9)
            elif d2 < 1.2:
                c = (230, 255, 255)
            elif d2 < tail_len:
                c = scale_rgb((30, 170, 255), (1.0 - d2 / tail_len) ** 1.9)
            else:
                c = (6, 4, 14)
            out.append(c)
        return out


class TwinkleEffect(HostEffect):
    info = EffectInfo("twinkle", "Starlight Twinkle", "Sparkle", "Deep purple/indigo backdrop with twinkling gold stars", 0.5)

    def __init__(self, *, speed: float = 0.5, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(42)
        self._levels: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._levels) != count:
            self._levels = [0.0] * count
        decay = 0.78 + (1.0 - self.speed) * 0.14
        spawn_p = 0.04 + self.speed * 0.12
        base = (45, 0, 95)
        star = (255, 235, 130)
        out: list[RGB] = []
        for i in range(count):
            self._levels[i] *= decay
            if self._rng.random() < spawn_p:
                self._levels[i] = 1.0
            out.append(interpolate_rgb(base, star, min(1.0, self._levels[i])))
        return out


class SparkleEffect(HostEffect):
    info = EffectInfo("sparkle", "Festive Sparkle", "Sparkle", "Crisp pink/aqua/white glints across random pixels", 0.6)

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(101)
        self._flash: list[tuple[RGB, float]] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._flash) != count:
            self._flash = [((0, 0, 0), 0.0)] * count
        palette: list[RGB] = [(255, 20, 145), (0, 240, 255), (255, 255, 255)]
        prob = 0.05 + self.speed * 0.18
        out: list[RGB] = []
        for i in range(count):
            col, lvl = self._flash[i]
            lvl *= 0.75
            if self._rng.random() < prob:
                col = self._rng.choice(palette)
                lvl = 1.0
            self._flash[i] = (col, lvl)
            out.append(scale_rgb(col, lvl) if lvl > 0.05 else (10, 18, 28))
        return out


class FireEffect(HostEffect):
    info = EffectInfo("fire", "Fireplace Embers", "Physics", "Per-pixel warm ember flicker simulation", 0.55)

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(7)
        self._heat: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._heat) != count:
            self._heat = [0.6] * count
        out: list[RGB] = []
        rate = 0.25 + self.speed * 0.5
        for i in range(count):
            target = self._rng.uniform(0.25, 1.0)
            self._heat[i] += (target - self._heat[i]) * rate
            h = self._heat[i]
            if h < 0.4:
                c = interpolate_rgb((60, 0, 0), (255, 45, 0), h / 0.4)
            elif h < 0.8:
                c = interpolate_rgb((255, 45, 0), (255, 150, 0), (h - 0.4) / 0.4)
            else:
                c = interpolate_rgb((255, 150, 0), (255, 240, 140), (h - 0.8) / 0.2)
            out.append(c)
        return out


class ThermalFlameEffect(HostEffect):
    info = EffectInfo("thermal_flame", "Thermal Flame", "Physics", "Turbulent multi-zone combustion simulation with hot blue wick pulses", 0.6)

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(99)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (3.0 + self.speed * 10.0)
        draft = 0.72 if self._rng.random() < 0.06 else 1.0
        out: list[RGB] = []
        for i in range(count):
            wave = 0.5 + 0.5 * math.sin(t + i * 0.6) * math.cos(t * 0.7 - i * 0.25)
            intensity = max(0.25, min(1.0, (0.55 + 0.45 * wave) * draft + self._rng.uniform(-0.12, 0.12)))
            if self._rng.random() < 0.015:
                out.append((90, 210, 255))
            else:
                hue = 0.015 + 0.085 * (intensity ** 1.5)
                out.append(_hsv(hue, 1.0, intensity))
        return out


class SnowfallEffect(HostEffect):
    info = EffectInfo("snowfall", "Snowfall", "Holiday", "Drifting icy white snowflakes fading softly across a winter blue ring", 0.45)

    def __init__(self, *, speed: float = 0.45, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(1225)
        self._snow: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._snow) != count:
            self._snow = [0.0] * count
        decay = 0.82 + (1.0 - self.speed) * 0.12
        for i in range(count):
            self._snow[i] *= decay
            if self._rng.random() < (0.03 + self.speed * 0.08):
                self._snow[i] = 1.0
        bg = (10, 35, 95)
        flake = (240, 250, 255)
        return [interpolate_rgb(bg, flake, min(1.0, self._snow[i])) for i in range(count)]


class WavesEffect(HostEffect):
    info = EffectInfo("waves", "Ocean Waves", "Ambient", "Smooth undulating aqua-to-cobalt traveling waves", 0.4)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (1.0 + self.speed * 5.0)
        out: list[RGB] = []
        for i in range(count):
            angle = (i / count) * 2.0 * math.pi * 2.0 - t
            v = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(angle))
            c = interpolate_rgb((0, 40, 140), (0, 240, 220), 0.5 + 0.5 * math.cos(angle * 0.5))
            out.append(scale_rgb(c, v))
        return out


class PulseEffect(HostEffect):
    info = EffectInfo("pulse", "Breathing Pulse", "Ambient", "Synchronized smooth sine breathing across all LEDs", 0.4)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        color: RGB = tuple(self.params.get("color", (0, 220, 255)))  # type: ignore[assignment]
        t = elapsed_s * (0.8 + self.speed * 4.0)
        b = 0.1 + 0.9 * (0.5 + 0.5 * math.sin(t))
        return [scale_rgb(color, b)] * count


class AlternatingEffect(HostEffect):
    info = EffectInfo("alternating", "Alternating Dual", "Holiday", "Crisp alternating two-color LEDs that swap in time", 0.5)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        c1: RGB = tuple(self.params.get("primary", (255, 0, 0)))  # type: ignore[assignment]
        c2: RGB = tuple(self.params.get("secondary", (0, 255, 0)))  # type: ignore[assignment]
        step = int(elapsed_s * (0.8 + self.speed * 5.0)) % 2
        return [c1 if (i + step) % 2 == 0 else c2 for i in range(count)]


class TheaterChaseEffect(HostEffect):
    info = EffectInfo("theater_chase", "Theater Chase", "Motion", "Classic 3-step marquee theater chase", 0.5)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        color: RGB = tuple(self.params.get("color", (255, 190, 40)))  # type: ignore[assignment]
        step = int(elapsed_s * (2.0 + self.speed * 14.0)) % 3
        return [color if (i % 3) == step else (0, 0, 0) for i in range(count)]


class ColorWipeEffect(HostEffect):
    info = EffectInfo("color_wipe", "Color Wipe", "Motion", "Progressive color sweep cycling through holiday hues", 0.55)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        palette: list[RGB] = [(255, 0, 0), (0, 255, 0), (0, 120, 255), (255, 220, 0), (255, 255, 255)]
        total_steps = elapsed_s * (6.0 + self.speed * 30.0)
        idx = int(total_steps // count)
        cur = palette[idx % len(palette)]
        prev = palette[(idx - 1) % len(palette)]
        pos = int(total_steps % count)
        return [cur if i <= pos else prev for i in range(count)]


class RandomPixelsEffect(HostEffect):
    info = EffectInfo("random_pixels", "Confetti Random", "Sparkle", "Per-pixel randomized jewel colors refreshed cleanly", 0.45)

    def __init__(self, *, speed: float = 0.45, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(314)
        self._last_step = -1
        self._buf: list[RGB] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        step = int(elapsed_s * (1.0 + self.speed * 8.0))
        if len(self._buf) != count or step != self._last_step:
            self._last_step = step
            self._buf = [_hsv(self._rng.random(), 1.0, self._rng.uniform(0.45, 1.0)) for _ in range(count)]
        return list(self._buf)


class CandyCaneEffect(HostEffect):
    info = EffectInfo("candy_cane", "Candy Cane", "Holiday", "Rotating red and bright white peppermint stripes", 0.5)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        shift = int(elapsed_s * (2.0 + self.speed * 14.0))
        return [(255, 0, 0) if ((i + shift) // 3) % 2 == 0 else (255, 255, 255) for i in range(count)]


class HollyEffect(HostEffect):
    info = EffectInfo("holly", "Holly & Berry", "Holiday", "Crimson berries and emerald pine segments pulsing softly", 0.45)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (1.0 + self.speed * 4.0)
        pulse = 0.65 + 0.35 * math.sin(t)
        shift = int(t * 0.7)
        out: list[RGB] = []
        for i in range(count):
            if ((i + shift) % 5) == 0:
                out.append(scale_rgb((255, 0, 0), min(1.0, pulse + 0.2)))
            else:
                out.append(scale_rgb((0, 210, 40), pulse))
        return out


class FrostyEffect(HostEffect):
    info = EffectInfo("frosty", "Frosty Shimmer", "Holiday", "Icy blue fade with gentle crystalline shimmer", 0.4)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (0.8 + self.speed * 3.5)
        out: list[RGB] = []
        for i in range(count):
            v = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(t + i * 0.35))
            out.append(interpolate_rgb((20, 90, 255), (170, 240, 255), v))
        return out


class PoliceSirenEffect(HostEffect):
    info = EffectInfo("police", "Police Lightbar", "Alert", "Split-ring alternating red/blue strobe arcs", 0.65)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        tick = int(elapsed_s * (4.0 + self.speed * 16.0)) % 6
        half = count // 2
        if tick in (0, 2):
            return [(255, 0, 0)] * half + [(0, 0, 20)] * (count - half)
        if tick in (3, 5):
            return [(20, 0, 0)] * half + [(0, 0, 255)] * (count - half)
        return [(255, 255, 255) if i % 4 == 0 else (0, 0, 0) for i in range(count)]


class ThunderstormEffect(HostEffect):
    info = EffectInfo("thunderstorm", "Thunderstorm", "Weather", "Deep storm-blue clouds with localized branching lightning flashes", 0.5)

    def __init__(self, *, speed: float = 0.5, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(555)
        self._bolt_end = 0.0
        self._bolt_start = 0
        self._bolt_len = 8

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if elapsed_s > self._bolt_end and self._rng.random() < (0.04 + self.speed * 0.08):
            self._bolt_end = elapsed_s + self._rng.uniform(0.08, 0.25)
            self._bolt_start = self._rng.randrange(count)
            self._bolt_len = self._rng.randint(5, max(6, count // 4))
        base = (8, 22, 110)
        if elapsed_s <= self._bolt_end:
            out = [base] * count
            for offset in range(self._bolt_len):
                out[(self._bolt_start + offset) % count] = (240, 248, 255)
            return out
        return [base] * count


class PlasmaEffect(HostEffect):
    info = EffectInfo("plasma", "Plasma Nebula", "Ambient", "Multi-harmonic flowing nebula interference colors", 0.45)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (0.5 + self.speed * 3.0)
        out: list[RGB] = []
        for i in range(count):
            a = i / count * 2.0 * math.pi
            v1 = math.sin(a * 2.0 + t)
            v2 = math.sin(a * 3.0 - t * 1.3)
            hue = (0.5 + 0.25 * (v1 + v2)) % 1.0
            val = 0.45 + 0.55 * (0.5 + 0.5 * math.cos(a + t * 0.8))
            out.append(_hsv(hue, 0.9, val))
        return out


class GravityBounceEffect(HostEffect):
    info = EffectInfo("gravity", "Gravity Bounce", "Physics", "Orbiting elastic ball accelerating under simulated gravity", 0.55)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        period = max(0.5, 2.2 - self.speed * 1.4)
        phase = (elapsed_s % period) / period
        # Parabolic bounce height 0..1
        height = 1.0 - (2.0 * phase - 1.0) ** 2
        pos = height * (count - 1)
        out: list[RGB] = []
        for i in range(count):
            dist = abs(i - pos)
            if dist < 2.5:
                out.append(scale_rgb((255, 110, 0), 1.0 - dist / 2.5))
            else:
                out.append((5, 2, 0))
        return out


class Fireplace2DEffect(HostEffect):
    """Spatial fireplace tailored to circular wreath geometry (bottom embers, rising side flames, top sparks)."""

    info = EffectInfo(
        "fireplace_2d",
        "2D Fireplace Hearth",
        "Physics",
        "Glowing bottom ember bed with rising flame tongues up both sides and top sparks",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(2026)
        self._sparks: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._sparks) != count:
            self._sparks = [0.0] * count
        bottom_idx = float(self.params.get("bottom_index", count * 0.22))
        t = elapsed_s * (2.5 + self.speed * 6.5)

        out: list[RGB] = []
        for i in range(count):
            # Angular distance from bottom (0.0 = bottom center, 1.0 = top center)
            delta = abs(((i - bottom_idx + count / 2.0) % count) - count / 2.0) / (count / 2.0)
            # Symmetric turbulence rising from bottom -> top
            flicker = (
                0.55
                + 0.25 * math.sin(t * 1.9 - delta * 5.5 + i * 0.3)
                + 0.20 * math.cos(t * 3.1 - delta * 7.0 - i * 0.5)
            )
            noise = self._rng.uniform(-0.14, 0.14)
            heat = max(0.0, min(1.2, (1.12 - delta * 1.15) * flicker + noise))

            # Random rising embers near upper half
            self._sparks[i] *= 0.72
            if delta > 0.45 and self._rng.random() < (0.015 + self.speed * 0.03):
                self._sparks[i] = 1.0

            if delta < 0.24:
                # Glowing red-orange hearth coals at bottom
                coal = max(0.35, min(1.0, 0.72 + 0.28 * math.sin(t * 1.2 + i) + noise * 0.6))
                col = interpolate_rgb((150, 12, 0), (255, 115, 5), coal)
            elif heat > 0.75:
                col = interpolate_rgb((255, 85, 0), (255, 215, 65), min(1.0, (heat - 0.75) / 0.4))
            elif heat > 0.22:
                col = interpolate_rgb((70, 5, 0), (255, 70, 0), (heat - 0.22) / 0.53)
            else:
                col = scale_rgb((120, 20, 0), max(0.04, heat / 0.22 * 0.35))

            if self._sparks[i] > 0.08:
                col = interpolate_rgb(col, (255, 190, 60), min(1.0, self._sparks[i]))
            out.append(col)
        return out


class ColorSwirlEffect(HostEffect):
    """Multi-ribbon colorful swirl rotating dynamically around the circular wreath."""

    info = EffectInfo(
        "color_swirl",
        "Multi-Color Swirl",
        "Spectrum",
        "Rich multi-harmonic color swirl with luminous white-gold crests",
        0.65,
    )

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        t = elapsed_s * (0.4 + self.speed * 1.8)
        out: list[RGB] = []
        for i in range(count):
            pos = i / count
            hue = (pos * 2.0 - t + 0.18 * math.sin(pos * 4.0 * math.pi + t * 2.3)) % 1.0
            crest = max(0.0, math.sin((pos * 3.0 - t * 1.6) * 2.0 * math.pi)) ** 4
            val = 0.55 + 0.45 * (0.5 + 0.5 * math.cos((pos * 2.0 + t * 1.2) * 2.0 * math.pi))
            sat = max(0.25, 1.0 - crest * 0.65)
            out.append(_hsv(hue, sat, min(1.0, val + crest * 0.35)))
        return out


class CosmicAuroraEffect(HostEffect):
    """Multi-layer spatial aurora plasma with counter-orbiting comets and starburst glints."""

    info = EffectInfo(
        "cosmic_aurora",
        "Cosmic Aurora & Comets",
        "Advanced",
        "Layered aurora interference + counter-rotating comets + diamond starburst glints",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(777)
        self._glint: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._glint) != count:
            self._glint = [0.0] * count
        t = elapsed_s * (0.7 + self.speed * 2.4)
        c1_head = (t * 8.5) % count
        c2_head = (-t * 6.0) % count
        tail_len = max(5, count // 6)

        out: list[RGB] = []
        for i in range(count):
            a = (i / count) * 2.0 * math.pi
            # Base aurora wave (emerald -> cyan -> violet -> magenta)
            wave = 0.5 + 0.5 * math.sin(a * 2.0 + t * 1.1) * math.cos(a * 3.0 - t * 0.7)
            aurora_h = (0.44 + 0.36 * wave + 0.06 * math.sin(t * 0.3)) % 1.0
            base = _hsv(aurora_h, 0.92, 0.38 + 0.35 * wave)

            # Orbiting Comet 1 (icy cyan-white)
            d1 = (c1_head - i) % count
            if d1 < tail_len:
                f1 = (1.0 - d1 / tail_len) ** 2.0
                c1_col = (240, 255, 255) if d1 < 1.2 else (0, 235, 255)
                base = interpolate_rgb(base, c1_col, min(1.0, f1 * 0.95))

            # Counter-orbiting Comet 2 (magenta-gold)
            d2 = (i - c2_head) % count
            if d2 < tail_len:
                f2 = (1.0 - d2 / tail_len) ** 2.0
                c2_col = (255, 240, 190) if d2 < 1.2 else (255, 30, 180)
                base = interpolate_rgb(base, c2_col, min(1.0, f2 * 0.9))

            # Occasional diamond spark
            self._glint[i] *= 0.7
            if self._rng.random() < 0.025:
                self._glint[i] = 1.0
            if self._glint[i] > 0.1:
                base = interpolate_rgb(base, (255, 255, 255), self._glint[i])

            out.append(base)
        return out


class LayeredPineHearthEffect(HostEffect):
    """True 3D fireplace: 6:00 bottom ember hearth, rising flames up left/right sides, 12:00 rising sparks."""

    info = EffectInfo(
        "layered_hearth",
        "Layered 3D Pine Hearth",
        "3D Wreath",
        "6:00 glowing ember bed with rising flames up both sides, buried pine coals, and 12:00 sparks",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(303)
        self._nodes = build_wreath_layout(50)
        self._sparks: list[float] = []

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        if len(self._sparks) != count:
            self._sparks = [0.0] * count
        t = elapsed_s * (2.6 + self.speed * 6.8)
        out: list[RGB] = []
        for node in self._nodes:
            # Height from bottom 6:00 (y=-1 -> h=0.0) to top 12:00 (y=+1 -> h=1.0)
            height = max(0.0, min(1.0, (node.y + 1.0) * 0.5))
            ang = math.radians(node.angle_deg)
            wave = (
                0.55
                + 0.25 * math.sin(t * 2.0 - height * 5.2 + ang * 2.0)
                + 0.20 * math.cos(t * 3.1 - height * 7.0 - ang * 3.0)
            )
            jitter = self._rng.uniform(-0.13, 0.13)
            heat = max(0.0, min(1.15, (1.15 - height * 1.1) * wave + jitter))

            self._sparks[node.index] *= 0.72
            if height > 0.58 and self._rng.random() < (0.015 + self.speed * 0.035):
                self._sparks[node.index] = 1.0

            if height < 0.22:
                # 6:00 bottom hearth coals (35,36,37,38,39,40,34)
                coal = max(0.35, min(1.0, 0.7 + 0.3 * math.sin(t * 1.4 + node.index) + jitter * 0.6))
                if node.layer == "back":
                    col = interpolate_rgb((130, 8, 0), (235, 55, 0), coal)
                elif node.layer == "inner":
                    col = (100, 210, 255) if self._rng.random() < 0.015 else interpolate_rgb((255, 110, 0), (255, 225, 85), coal)
                else:
                    col = interpolate_rgb((220, 35, 0), (255, 165, 25), coal)
            elif node.layer == "back":
                # Deep pine ember underglow through branches
                col = scale_rgb((220, 42, 0), max(0.08, heat * 0.65))
            elif heat > 0.72:
                col = interpolate_rgb((255, 95, 0), (255, 235, 115), min(1.0, (heat - 0.72) / 0.42))
            elif heat > 0.20:
                col = interpolate_rgb((80, 6, 0), (255, 75, 0), (heat - 0.20) / 0.52)
            else:
                col = scale_rgb((110, 15, 0), max(0.04, heat / 0.20 * 0.35))

            if self._sparks[node.index] > 0.08:
                col = interpolate_rgb(col, (255, 195, 65), min(1.0, self._sparks[node.index]))
            out.append(col)
        return out


class ClockSweepRadarEffect(HostEffect):
    """True clockwise polar sweep calibrated by wreath clock-hour angles and depth layers."""

    info = EffectInfo(
        "clock_sweep",
        "Polar Clock Sweep",
        "3D Wreath",
        "Sweeps cleanly by physical clock angle (12->3->6->9) with contrasting inner-ring halo",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        sweep_deg = (elapsed_s * (70.0 + self.speed * 260.0)) % 360.0
        hue_shift = (elapsed_s * 0.08) % 1.0
        out: list[RGB] = []
        for node in self._nodes:
            dist = (sweep_deg - node.angle_deg) % 360.0
            if dist < 95.0:
                fade = (1.0 - dist / 95.0) ** 1.6
                if node.layer == "inner":
                    col = interpolate_rgb((0, 90, 160), (220, 255, 255), fade)
                elif node.layer == "back":
                    col = scale_rgb(_hsv((hue_shift + 0.55) % 1.0, 1.0, 0.7), fade)
                else:
                    col = scale_rgb(_hsv((node.angle_deg / 360.0 + hue_shift) % 1.0, 1.0, 1.0), fade)
            else:
                if node.layer == "back":
                    col = (0, 32, 10)
                elif node.layer == "inner":
                    col = (0, 18, 45)
                else:
                    col = (4, 4, 12)
            out.append(col)
        return out


class DualRingSpinEffect(HostEffect):
    """Counter-rotating 3D rings: Inner ring spins CCW in icy cyan/violet; outer/front spins CW in rainbow gold; back glows pine."""

    info = EffectInfo(
        "ring_counter_spin",
        "3D Dual-Ring Counter-Spin",
        "3D Wreath",
        "Inner ring orbits counter-clockwise while front/outer crown swirls clockwise over breathing pine backlight",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        t = elapsed_s * (65.0 + self.speed * 240.0)
        cw_deg = t % 360.0
        ccw_deg = (-t * 1.25) % 360.0
        hue_base = (elapsed_s * 0.14) % 1.0

        out: list[RGB] = []
        for node in self._nodes:
            if node.layer == "inner":
                d = (node.angle_deg - ccw_deg) % 360.0
                if d < 130.0:
                    fade = (1.0 - d / 130.0) ** 1.5
                    out.append(interpolate_rgb((35, 0, 110), (190, 250, 255), fade))
                else:
                    out.append((12, 0, 40))
            elif node.layer == "back":
                breath = 0.25 + 0.45 * (0.5 + 0.5 * math.sin(elapsed_s * 1.8 + math.radians(node.angle_deg)))
                out.append(scale_rgb((0, 220, 75), breath))
            else:
                # Front / Outer crown spins clockwise through rich rainbow
                d = (cw_deg - node.angle_deg) % 360.0
                hue = (node.angle_deg / 360.0 - elapsed_s * (0.2 + self.speed * 0.8)) % 1.0
                boost = 1.0 if d < 90.0 else 0.55
                out.append(_hsv((hue + hue_base * 0.2) % 1.0, 1.0, boost))
        return out


class PolarSpiralVortexEffect(HostEffect):
    """True 2D polar spiral vortex using physical angle + radial ring depth."""

    info = EffectInfo(
        "polar_vortex",
        "2D Polar Vortex Swirl",
        "3D Wreath",
        "Pinwheel spiral twisting continuously across radial rings and clock angles",
        0.65,
    )

    def __init__(self, *, speed: float = 0.65, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        spin = elapsed_s * (0.45 + self.speed * 1.8)
        out: list[RGB] = []
        for node in self._nodes:
            # Twist hue & brightness by both clock angle and radial depth
            spiral_phase = (node.angle_deg / 180.0 + node.radius * 0.65 - spin) % 1.0
            crest = max(0.0, math.sin(spiral_phase * 2.0 * math.pi)) ** 2
            val = 0.35 + 0.65 * crest
            if node.layer == "back":
                val *= 0.6
            out.append(_hsv((spiral_phase + elapsed_s * 0.1) % 1.0, 1.0 - crest * 0.2, val))
        return out


class NorthernLights3DEffect(HostEffect):
    """2D Cartesian (x, y) aurora curtains cascading from 12:00 top down to 6:00 bottom."""

    info = EffectInfo(
        "aurora_3d",
        "3D Northern Lights",
        "3D Wreath",
        "True 2D (x, y) aurora curtains cascading vertically across the wreath",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        t = elapsed_s * (0.8 + self.speed * 2.6)
        out: list[RGB] = []
        for node in self._nodes:
            curtain = 0.5 + 0.5 * math.sin(node.x * 2.8 + t) * math.cos(node.y * 2.4 - t * 0.65)
            # Aurora palette: emerald (0.38) -> cyan (0.50) -> violet (0.78)
            hue = (0.36 + 0.42 * curtain + 0.08 * node.y) % 1.0
            val = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(node.y * 3.0 + t * 1.3))
            if node.layer == "inner":
                sat = 0.78
                val = min(1.0, val + 0.15)
            elif node.layer == "back":
                sat = 1.0
                val *= 0.65
            else:
                sat = 0.96
            out.append(_hsv(hue, sat, val))
        return out


class Candle3DEffect(HostEffect):
    """Physics-based 3D pillar candle: beeswax lower ring, sapphire combustion core at 11/15, swaying 12:00 flame."""

    info = EffectInfo(
        "candle_3d",
        "3D Pillar Candle",
        "3D Physics",
        "Glowing molten wax base, sapphire wick core below top crown, and wind-swaying 12:00 flame",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(1826)
        self._nodes = build_wreath_layout(50)
        self._gust = 0.0

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        t = elapsed_s * (2.0 + self.speed * 5.0)
        # Occasional wind draft perturbing the flame sway laterally
        if self._rng.random() < (0.04 + self.speed * 0.05):
            self._gust += self._rng.uniform(-0.35, 0.35)
        self._gust *= 0.86
        flame_x = 0.22 * math.sin(t * 2.1) + 0.08 * math.sin(t * 4.7) + self._gust
        flame_x = max(-0.5, min(0.5, flame_x))
        flame_bright = max(0.65, min(1.1, 0.92 + 0.14 * math.sin(t * 5.3) - abs(self._gust) * 0.4))

        out: list[RGB] = []
        for node in self._nodes:
            # 12:00 flame crown region (top inner wick vs swaying orange-white flame)
            if node.y > 0.42:
                dx = abs(node.x - flame_x)
                if node.layer == "inner" and node.y < 0.72:
                    # Hot oxygen-rich sapphire-blue wick base (LED 11 & 15)
                    col = interpolate_rgb((40, 110, 255), (255, 190, 90), max(0.0, 0.45 - dx))
                elif node.layer == "back":
                    # Warm pine halo behind the candle flame
                    col = scale_rgb((255, 90, 10), max(0.25, 0.7 * flame_bright - dx * 0.4))
                else:
                    # Luminous white-gold flame body swaying with flame_x
                    heat = max(0.2, min(1.0, (1.0 - dx * 1.15) * flame_bright))
                    if heat > 0.78:
                        col = interpolate_rgb((255, 185, 45), (255, 245, 200), (heat - 0.78) / 0.22)
                    else:
                        col = interpolate_rgb((200, 55, 0), (255, 185, 45), heat / 0.78)
            else:
                # Radiant beeswax pillar glowing warmly downward from top flame
                wax_glow = max(0.18, 0.38 + 0.35 * ((node.y + 1.0) * 0.5)) * (0.94 + 0.06 * math.sin(t * 3.0))
                if node.layer == "back":
                    wax_glow *= 0.65
                col = scale_rgb((255, 130, 32), min(1.0, wax_glow))
            out.append(col)
        return out


class ConvectionFire3DEffect(HostEffect):
    """Stateful thermal buoyancy & blackbody cooling fire climbing both sides of the wreath."""

    info = EffectInfo(
        "convection_fire_3d",
        "Thermal Convection Fire",
        "3D Physics",
        "Real buoyant thermal parcels rising from 6:00 coals up both wreath arcs with blackbody cooling",
        0.65,
    )

    def __init__(self, *, speed: float = 0.65, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(451)
        self._nodes = build_wreath_layout(50)
        self._temp: list[float] = [0.2] * 50
        self._parcels: list[list[float]] = []  # [side (-1/+1), height (-1..+1.1), heat, vel]

    @staticmethod
    def _blackbody(temp: float) -> RGB:
        t = max(0.0, min(1.0, temp))
        if t < 0.25:
            return interpolate_rgb((18, 0, 0), (165, 10, 0), t / 0.25)
        if t < 0.55:
            return interpolate_rgb((165, 10, 0), (255, 85, 0), (t - 0.25) / 0.30)
        if t < 0.82:
            return interpolate_rgb((255, 85, 0), (255, 195, 35), (t - 0.55) / 0.27)
        return interpolate_rgb((255, 195, 35), (255, 250, 210), (t - 0.82) / 0.18)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
            self._temp = [0.2] * count

        dt = 0.05 + self.speed * 0.06
        # Spawn buoyant fire parcels from 6:00 hearth
        if len(self._parcels) < 16 and self._rng.random() < (0.35 + self.speed * 0.45):
            side = -1.0 if self._rng.random() < 0.5 else 1.0
            self._parcels.append([side, -0.95, self._rng.uniform(0.75, 1.05), self._rng.uniform(0.45, 0.9)])

        alive: list[list[float]] = []
        for p in self._parcels:
            p[3] += 0.85 * p[2] * dt  # buoyant acceleration
            p[1] += p[3] * dt
            p[2] -= (0.28 + 0.12 * max(0.0, p[1])) * dt  # radiative cooling
            if p[1] <= 1.15 and p[2] > 0.08:
                alive.append(p)
        self._parcels = alive

        out: list[RGB] = []
        for node in self._nodes:
            target = 0.0
            if node.y < -0.58:
                # 6:00 blazing ember hearth bed
                target = 0.62 + 0.25 * math.sin(elapsed_s * 5.0 + node.index) + self._rng.uniform(-0.1, 0.15)
            for side, py, pheat, _ in self._parcels:
                # Parcel climbs left (x <= 0) or right (x >= 0) arc
                if (side < 0 and node.x <= 0.25) or (side > 0 and node.x >= -0.25):
                    dy = abs(node.y - py)
                    if dy < 0.38:
                        target = max(target, pheat * (1.0 - dy / 0.38))

            # Back pine LEDs hold thermal inertia longer (smoldering coals inside branches)
            inertia = 0.86 if node.layer == "back" else 0.58
            self._temp[node.index] = self._temp[node.index] * inertia + target * (1.0 - inertia)
            scale = 0.72 if node.layer == "back" else 1.0
            col = self._blackbody(self._temp[node.index])
            out.append(scale_rgb(col, scale))
        return out


class PendulumShockwave3DEffect(HostEffect):
    """Nonlinear swinging gravity pendulum triggering elastic radial/arc shockwaves at turnarounds."""

    info = EffectInfo(
        "pendulum_wave_3d",
        "Gravity Pendulum & Shockwaves",
        "3D Physics",
        "RK2 gravity pendulum swinging across the wreath, emitting shockwaves on turnaround",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)
        self._theta = 1.45  # radians from bottom (6:00 = 0, +pi/2 = 3:00, -pi/2 = 9:00)
        self._omega = 0.0
        self._last_sign = 1
        self._waves: list[tuple[float, float, RGB]] = []  # (origin_angle_deg, radius_deg, color)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        dt = 0.04 + self.speed * 0.06
        g_over_l = 9.8
        # RK2 step with gentle energy-preserving drive
        k1_a = -g_over_l * math.sin(self._theta)
        mid_th = self._theta + 0.5 * dt * self._omega
        mid_om = self._omega + 0.5 * dt * k1_a
        k2_a = -g_over_l * math.sin(mid_th)
        self._theta += dt * mid_om
        self._omega += dt * k2_a
        # Subtle magnetic kicker at bottom so amplitude stays lively
        if abs(self._theta) < 0.25:
            self._omega += math.copysign(0.18, self._omega or 1.0) * dt

        cur_sign = 1 if self._omega >= 0 else -1
        if cur_sign != self._last_sign:
            self._last_sign = cur_sign
            impact_deg = (180.0 - math.degrees(self._theta)) % 360.0
            col = (0, 245, 255) if self._theta > 0 else (255, 40, 200)
            self._waves.append((impact_deg, 1.0, col))

        next_waves: list[tuple[float, float, RGB]] = []
        for ang, rad, col in self._waves:
            rad += 18.0 + self.speed * 20.0
            if rad < 200.0:
                next_waves.append((ang, rad, col))
        self._waves = next_waves

        pend_deg = (180.0 - math.degrees(self._theta)) % 360.0
        out: list[RGB] = []
        for node in self._nodes:
            col: RGB = (6, 8, 22) if node.layer != "back" else (12, 0, 28)
            # Shockwave rings
            for w_ang, w_rad, w_col in self._waves:
                d = abs(((node.angle_deg - w_ang + 180.0) % 360.0) - 180.0)
                ring_dist = abs(d - w_rad)
                if ring_dist < 28.0:
                    fade = (1.0 - ring_dist / 28.0) * max(0.0, 1.0 - w_rad / 200.0)
                    col = interpolate_rgb(col, w_col, min(1.0, fade * 1.2))
            # Pendulum bob mass
            bob_d = abs(((node.angle_deg - pend_deg + 180.0) % 360.0) - 180.0)
            if bob_d < 26.0:
                glow = (1.0 - bob_d / 26.0) ** 1.4
                bob_col = (255, 250, 200) if node.layer == "inner" else (255, 165, 20)
                col = interpolate_rgb(col, bob_col, glow)
            out.append(col)
        return out


class QuantumInterference3DEffect(HostEffect):
    """2D wave interference between two orbiting emitters across true (x, y, radial_depth) wreath positions."""

    info = EffectInfo(
        "quantum_interference_3d",
        "Quantum Wave Interference",
        "3D Experimental",
        "Two orbiting phase emitters create constructive/destructive 3D wave fringes across pine layers",
        0.6,
    )

    def __init__(self, *, speed: float = 0.6, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        t = elapsed_s * (1.2 + self.speed * 3.8)
        e1_x, e1_y = 0.75 * math.cos(t * 0.9), 0.75 * math.sin(t * 0.9)
        e2_x, e2_y = 0.75 * math.cos(-t * 1.27), 0.75 * math.sin(-t * 1.27)
        k = 7.5
        out: list[RGB] = []
        for node in self._nodes:
            z = 0.25 if node.layer == "back" else (0.0 if node.layer == "front" else -0.2)
            d1 = math.sqrt((node.x - e1_x) ** 2 + (node.y - e1_y) ** 2 + z ** 2)
            d2 = math.sqrt((node.x - e2_x) ** 2 + (node.y - e2_y) ** 2 + z ** 2)
            psi = 0.5 * (math.sin(k * d1 - t * 2.5) + math.sin(k * d2 - t * 2.9))
            # Map amplitude [-1, 1] -> deep indigo nodes to blazing cyan/gold antinodes
            mag = abs(psi)
            hue = (0.52 + 0.35 * psi + elapsed_s * 0.05) % 1.0
            sat = 0.95 - 0.35 * (mag ** 3)
            val = 0.06 + 0.94 * (mag ** 1.5)
            out.append(_hsv(hue, sat, val))
        return out


class JacobsLadder3DEffect(HostEffect):
    """High-voltage plasma arcs climbing simultaneously up both sides from 6:00 to snap at 12:00."""

    info = EffectInfo(
        "jacobs_ladder_3d",
        "Tesla Jacob's Ladder",
        "3D Experimental",
        "Twin plasma arcs climb from 6:00 electrodes across inner/front/outer layers and snap at 12:00",
        0.65,
    )

    def __init__(self, *, speed: float = 0.65, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(9001)
        self._nodes = build_wreath_layout(50)
        self._arc_y = -0.95
        self._flash = 0.0
        self._afterglow: list[float] = [0.0] * 50

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
            self._afterglow = [0.0] * count

        self._arc_y += (0.06 + self.speed * 0.14)
        self._flash *= 0.68
        if self._arc_y > 1.05:
            self._arc_y = -0.95
            self._flash = 1.0

        # Active depth layer crackles stochastically as arc climbs
        arc_layer = self._rng.choice(("inner", "front", "outer"))
        out: list[RGB] = []
        for node in self._nodes:
            self._afterglow[node.index] *= 0.78
            dy = abs(node.y - self._arc_y)
            col: RGB = (10, 4, 28) if node.layer == "back" else (3, 2, 10)

            # Bottom 6:00 high-voltage electrodes
            if node.y < -0.78:
                col = (90, 60, 255)

            # Climbing plasma arc bridging left & right horns
            if dy < 0.24:
                intensity = (1.0 - dy / 0.24) * (1.0 if node.layer == arc_layer else 0.55)
                if self._rng.random() < 0.85:
                    self._afterglow[node.index] = max(self._afterglow[node.index], intensity)
                    col = interpolate_rgb(col, (210, 240, 255), intensity)

            # Top 12:00 arc snap corona discharge
            if self._flash > 0.08 and node.y > 0.65:
                col = interpolate_rgb(col, (255, 220, 255), self._flash)

            # UV ozone pine afterglow
            if self._afterglow[node.index] > 0.05:
                glow_col = (130, 30, 255) if node.layer == "back" else (40, 170, 255)
                col = interpolate_rgb(col, glow_col, min(0.8, self._afterglow[node.index] * 0.65))

            out.append(col)
        return out


class BlackHoleAccretion3DEffect(HostEffect):
    """Keplerian differential rotation (inner ring orbits faster), Doppler beaming, and polar jets."""

    info = EffectInfo(
        "black_hole_3d",
        "Relativistic Black Hole",
        "3D Experimental",
        "Differential Keplerian orbits (inner faster than outer), Doppler blue/redshift, and 12/6 polar jets",
        0.65,
    )

    def __init__(self, *, speed: float = 0.65, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(4200)
        self._nodes = build_wreath_layout(50)
        self._jet_energy = 0.0

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        if self._jet_energy < 0.05 and self._rng.random() < 0.04:
            self._jet_energy = 1.0
        self._jet_energy *= 0.85

        t = elapsed_s * (0.8 + self.speed * 3.0)
        out: list[RGB] = []
        for node in self._nodes:
            # Keplerian angular velocity omega ~ r^(-1.5): inner ring spins ~2.4x faster than outer!
            omega = 1.0 / (node.radius ** 1.5)
            phase = (node.angle_deg / 180.0 - t * omega * 0.5) % 1.0
            stream = 0.25 + 0.75 * (max(0.0, math.sin(phase * 2.0 * math.pi)) ** 2)

            # Relativistic Doppler shift: approaching side (x > 0) blueshifted, receding (x < 0) redshifted
            doppler = (node.x + 1.0) * 0.5  # 0.0 left (red) .. 1.0 right (blue-white)
            if node.layer == "back":
                col = scale_rgb((110, 10, 210), 0.25 + 0.45 * stream)
            elif node.layer == "inner":
                # Scorching inner event horizon ring
                col = interpolate_rgb((255, 120, 40), (190, 240, 255), doppler)
                col = scale_rgb(col, min(1.0, 0.45 + 0.55 * stream))
            else:
                receding = (255, 55, 10)
                approaching = (60, 210, 255)
                col = scale_rgb(interpolate_rgb(receding, approaching, doppler), stream)

            # Polar relativistic flare jets shooting out 12:00 and 6:00
            if self._jet_energy > 0.1 and abs(node.x) < 0.24 and abs(node.y) > 0.75:
                col = interpolate_rgb(col, (255, 255, 255), self._jet_energy)
            out.append(col)
        return out


class BioluminescentReef3DEffect(HostEffect):
    """Autonomous inner/outer light organisms crawling across the wreath with mating flashes over pine algae."""

    info = EffectInfo(
        "bioluminescent_3d",
        "Bioluminescent 3D Reef",
        "3D Experimental",
        "Autonomous creatures orbit inner & outer rings, flashing bioluminescent pulses when they pass",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)
        # (angle_deg, velocity_deg_s, layer_group, color)
        self._creatures = [
            [0.0,   42.0,  "inner", (0, 255, 220)],
            [180.0, 56.0,  "inner", (140, 255, 80)],
            [90.0,  -35.0, "outer", (255, 60, 200)],
            [270.0, -48.0, "outer", (255, 185, 30)],
        ]

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        rate = 0.4 + self.speed * 1.8
        pos_list: list[tuple[float, str, RGB]] = []
        for ang0, vel, grp, col in self._creatures:
            pos_list.append(((ang0 + elapsed_s * vel * rate) % 360.0, grp, col))

        # Check inner-to-outer rendezvous proximity for golden mating pulse
        rendezvous: list[float] = []
        for a1, g1, _ in pos_list:
            for a2, g2, _ in pos_list:
                if g1 != g2:
                    if abs(((a1 - a2 + 180.0) % 360.0) - 180.0) < 18.0:
                        rendezvous.append(a1)

        out: list[RGB] = []
        for node in self._nodes:
            if node.layer == "back":
                # Breathing deep-sea emerald/teal algae behind pine needles
                algae = 0.15 + 0.30 * (0.5 + 0.5 * math.sin(elapsed_s * 1.4 + math.radians(node.angle_deg * 2)))
                col: RGB = scale_rgb((0, 200, 130), algae)
            else:
                col = (2, 10, 22)

            for c_ang, c_grp, c_rgb in pos_list:
                matches_layer = (node.layer == "inner" and c_grp == "inner") or (node.layer != "inner" and c_grp == "outer")
                if matches_layer:
                    d = abs(((node.angle_deg - c_ang + 180.0) % 360.0) - 180.0)
                    if d < 36.0:
                        glow = (1.0 - d / 36.0) ** 1.6
                        col = interpolate_rgb(col, c_rgb, min(1.0, glow))

            for r_ang in rendezvous:
                d = abs(((node.angle_deg - r_ang + 180.0) % 360.0) - 180.0)
                if d < 42.0:
                    col = interpolate_rgb(col, (255, 245, 130), (1.0 - d / 42.0) * 0.9)
            out.append(col)
        return out


class FireflyFlight3DEffect(HostEffect):
    """Single lifelike firefly flying smoothly through 3D (x, y, depth) wreath branches with luciferin flashes."""

    info = EffectInfo(
        "firefly_3d",
        "3D Wandering Firefly",
        "3D Nature",
        "Lifelike firefly weaving between inner/front/outer/back pine branches with hover-dart flight & warm flashes",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(2027)
        self._nodes = build_wreath_layout(50)
        self._ang = 0.0
        self._ang_vel = 45.0
        self._rad = 0.78
        self._z = 0.0  # -0.3 inner/front .. +0.35 buried back
        self._hover_until = 0.0
        self._flash_phase = 0.0
        self._trail: list[float] = [0.0] * 50

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
            self._trail = [0.0] * count

        dt = 0.06 + self.speed * 0.05
        # Alternate between hovering near a branch and darting around the wreath
        if elapsed_s < self._hover_until:
            self._ang_vel *= 0.85
        else:
            if self._rng.random() < 0.04:
                self._hover_until = elapsed_s + self._rng.uniform(0.7, 1.6)
            else:
                target_vel = self._rng.choice((-1.0, 1.0, 1.0)) * (45.0 + self.speed * 110.0)
                self._ang_vel += (target_vel - self._ang_vel) * 0.14

        self._ang = (self._ang + self._ang_vel * dt) % 360.0
        self._rad = 0.76 + 0.21 * math.sin(elapsed_s * 1.4)
        self._z = 0.25 * math.sin(elapsed_s * 0.95)
        fx = self._rad * math.sin(math.radians(self._ang))
        fy = self._rad * math.cos(math.radians(self._ang))

        # Asymmetric biological firefly flash (quick ignition, soft warm decay)
        cycle = (elapsed_s * (0.65 + self.speed * 0.75)) % 1.0
        if cycle < 0.14:
            luciferin = (cycle / 0.14) ** 0.6
        elif cycle < 0.72:
            luciferin = max(0.18, math.exp(-(cycle - 0.14) * 4.5))
        else:
            luciferin = 0.18 + 0.08 * math.sin(elapsed_s * 8.0)

        fly_col = interpolate_rgb((155, 220, 20), (225, 255, 75), luciferin)

        out: list[RGB] = []
        for node in self._nodes:
            nz = 0.28 if node.layer == "back" else (-0.15 if node.layer == "inner" else 0.0)
            dist = math.sqrt((node.x - fx) ** 2 + (node.y - fy) ** 2 + (nz - self._z) ** 2)
            self._trail[node.index] *= 0.76
            if dist < 0.42:
                prox = (1.0 - dist / 0.42) ** 1.5
                self._trail[node.index] = max(self._trail[node.index], prox * (0.4 + 0.6 * luciferin))

            # Subtle moonlit forest pine backdrop
            base: RGB = (1, 16, 6) if node.layer == "back" else (2, 7, 14)
            glow = self._trail[node.index]
            if glow > 0.03:
                col = interpolate_rgb(base, fly_col, min(1.0, glow))
            else:
                col = base
            out.append(col)
        return out


class FireflySwarm3DEffect(HostEffect):
    """Swarm of 3 independent fireflies drifting through moonlit 3D pine branches."""

    info = EffectInfo(
        "firefly_swarm_3d",
        "Moonlit Firefly Swarm",
        "3D Nature",
        "Three independent fireflies weaving across depths over cool moonlit pine foliage",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)
        # (ang0, vel_deg_s, rad_freq, flash_freq, phase_off, color)
        self._flies = [
            (0.0,   52.0,  1.1, 0.75, 0.0, (205, 255, 55)),
            (130.0, -41.0, 1.5, 0.90, 0.37, (255, 215, 45)),
            (250.0, 68.0,  0.8, 0.62, 0.68, (150, 255, 95)),
        ]

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        rate = 0.45 + self.speed * 1.4
        positions: list[tuple[float, float, float, float, RGB]] = []
        for a0, vel, rfreq, ffreq, poff, col in self._flies:
            ang = (a0 + elapsed_s * vel * rate + 22.0 * math.sin(elapsed_s * 0.9 + poff * 6.0)) % 360.0
            rad = 0.76 + 0.20 * math.sin(elapsed_s * rfreq + poff * 5.0)
            fz = 0.25 * math.cos(elapsed_s * (rfreq * 0.7) + poff * 4.0)
            fx = rad * math.sin(math.radians(ang))
            fy = rad * math.cos(math.radians(ang))
            cyc = ((elapsed_s * ffreq * rate) + poff) % 1.0
            pulse = (cyc / 0.15) if cyc < 0.15 else max(0.15, math.exp(-(cyc - 0.15) * 4.2))
            positions.append((fx, fy, fz, pulse, col))

        out: list[RGB] = []
        for node in self._nodes:
            nz = 0.26 if node.layer == "back" else (-0.15 if node.layer == "inner" else 0.0)
            # Soft moonlight top edge + pine shadow back
            if node.layer == "back":
                col: RGB = (1, 14, 7)
            elif node.y > 0.3:
                col = scale_rgb((25, 45, 95), 0.35 * node.y)
            else:
                col = (2, 6, 16)

            for fx, fy, fz, pulse, fcol in positions:
                d = math.sqrt((node.x - fx) ** 2 + (node.y - fy) ** 2 + (nz - fz) ** 2)
                if d < 0.44:
                    strength = ((1.0 - d / 0.44) ** 1.6) * pulse
                    col = interpolate_rgb(col, fcol, min(1.0, strength))
            out.append(col)
        return out


class RipplePond3DEffect(HostEffect):
    """2D Euclidean water-drop ripples expanding radially across the entire 3D wreath."""

    info = EffectInfo(
        "ripple_pond_3d",
        "2D Raindrop Ripples",
        "3D Experimental",
        "True 2D circular shockwaves expanding across inner, front, outer, and back layers from random drops",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._rng = random.Random(808)
        self._nodes = build_wreath_layout(50)
        self._ripples: list[list[float]] = []  # [x0, y0, radius, hue]

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        if len(self._ripples) < 3 and self._rng.random() < (0.04 + self.speed * 0.07):
            node = self._rng.choice(self._nodes)
            self._ripples.append([node.x, node.y, 0.0, self._rng.choice((0.50, 0.56, 0.78))])

        dr = 0.045 + self.speed * 0.09
        alive: list[list[float]] = []
        for r in self._ripples:
            r[2] += dr
            if r[2] < 2.2:
                alive.append(r)
        self._ripples = alive

        out: list[RGB] = []
        for node in self._nodes:
            col: RGB = (2, 12, 30) if node.layer != "back" else (0, 8, 22)
            for rx, ry, rr, rhue in self._ripples:
                d = math.hypot(node.x - rx, node.y - ry)
                band = abs(d - rr)
                if band < 0.28:
                    amp = (1.0 - band / 0.28) * max(0.0, 1.0 - rr / 2.2)
                    crest = _hsv(rhue, 0.55 if amp > 0.65 else 0.95, 1.0)
                    col = interpolate_rgb(col, crest, min(1.0, amp * 1.15))
            out.append(col)
        return out


class HeartbeatCardiac3DEffect(HostEffect):
    """Physiological LUB-DUB heartbeat pulsing radially from inner ring outward to front/outer crown."""

    info = EffectInfo(
        "heartbeat_3d",
        "3D Living Heartbeat",
        "3D Physics",
        "LUB-DUB cardiac cycle: inner ring contracts first, ejecting crimson arterial wave to outer crown",
        0.5,
    )

    def __init__(self, *, speed: float = 0.5, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        bpm = 52.0 + self.speed * 68.0
        phase = (elapsed_s * (bpm / 60.0)) % 1.0

        # Double-peak Gaussian LUB (0.12) + DUB (0.30)
        lub = math.exp(-((phase - 0.12) / 0.045) ** 2)
        dub = math.exp(-((phase - 0.30) / 0.065) ** 2)

        out: list[RGB] = []
        for node in self._nodes:
            if node.layer == "inner":
                lvl = 0.12 + 0.88 * max(lub, dub * 0.45)
                col = interpolate_rgb((45, 0, 10), (255, 45, 95), lvl)
            elif node.layer == "back":
                lvl = 0.10 + 0.65 * (0.4 * lub + 0.7 * dub)
                col = scale_rgb((140, 0, 20), lvl)
            else:
                # Front & outer radiate slightly delayed from 12:00 down to 6:00 on DUB
                delay = (1.0 - node.y) * 0.04
                wave = math.exp(-((phase - (0.30 + delay)) / 0.07) ** 2)
                lvl = 0.08 + 0.92 * max(lub * 0.35, wave)
                col = interpolate_rgb((35, 0, 8), (255, 15, 45), lvl)
            out.append(col)
        return out


class DNAHelix3DEffect(HostEffect):
    """Twisting 3D double helix alternating between front/outer and back pine depth layers."""

    info = EffectInfo(
        "dna_helix_3d",
        "3D Twisting DNA Helix",
        "3D Experimental",
        "Counter-phased cyan & coral helix strands weaving front-to-back with golden inner rungs",
        0.55,
    )

    def __init__(self, *, speed: float = 0.55, **params: Any) -> None:
        super().__init__(speed=speed, **params)
        self._nodes = build_wreath_layout(50)

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        if len(self._nodes) != count:
            self._nodes = build_wreath_layout(count)
        t = elapsed_s * (1.2 + self.speed * 3.8)
        out: list[RGB] = []
        for node in self._nodes:
            ang = math.radians(node.angle_deg) * 3.0 - t
            # Two strands 180 deg apart in depth z_wave (-1 back .. +1 front/outer)
            s1 = math.sin(ang)
            s2 = -s1
            if node.layer == "inner":
                # Glowing golden hydrogen-bond base-pair rungs when strands cross
                rung = max(0.0, 1.0 - abs(s1) * 2.2)
                col = interpolate_rgb((8, 12, 30), (255, 210, 60), rung)
            elif node.layer == "back":
                b1 = max(0.0, -s1) ** 1.4
                b2 = max(0.0, -s2) ** 1.4
                c1 = scale_rgb((0, 210, 255), b1)
                c2 = scale_rgb((255, 50, 120), b2)
                col = (min(255, c1[0] + c2[0]), min(255, c1[1] + c2[1]), min(255, c1[2] + c2[2]))
            else:
                f1 = max(0.0, s1) ** 1.4
                f2 = max(0.0, s2) ** 1.4
                c1 = scale_rgb((0, 240, 255), f1)
                c2 = scale_rgb((255, 65, 130), f2)
                col = (min(255, c1[0] + c2[0]), min(255, c1[1] + c2[1]), min(255, c1[2] + c2[2]))
            out.append(col)
        return out


class KeyframeSequenceEffect(HostEffect):
    info = EffectInfo("keyframe_sequence", "Timeline Sequence", "Custom", "User-authored keyframe timeline playback", 0.5)

    def __init__(self, timeline: TimelineAnimation, *, speed: float = 0.5) -> None:
        super().__init__(speed=speed)
        if not timeline.keyframes:
            raise ValidationError("TimelineAnimation must contain at least one keyframe")
        self.timeline = timeline

    def render(self, count: int, elapsed_s: float, frame_index: int) -> list[RGB]:
        kfs = self.timeline.keyframes
        # Speed scales playback rate from 0.25x (speed=0) to 2.0x (speed=1)
        rate = 0.25 + self.speed * 1.75
        total_ms = sum(kf.duration_ms for kf in kfs)
        if total_ms <= 0:
            return _fit_pixels(kfs[0].pixels, count)

        t_ms = elapsed_s * 1000.0 * rate
        if self.timeline.loop:
            t_ms = t_ms % total_ms
        elif t_ms >= total_ms:
            return _fit_pixels(kfs[-1].pixels, count)

        acc = 0.0
        for idx, kf in enumerate(kfs):
            if t_ms < acc + kf.duration_ms or idx == len(kfs) - 1:
                cur_px = _fit_pixels(kf.pixels, count)
                if kf.transition == "cut" or (idx == len(kfs) - 1 and not self.timeline.loop):
                    return cur_px
                nxt = kfs[(idx + 1) % len(kfs)]
                nxt_px = _fit_pixels(nxt.pixels, count)
                frac = (t_ms - acc) / max(1.0, float(kf.duration_ms))
                return [interpolate_rgb(a, b, frac) for a, b in zip(cur_px, nxt_px)]
            acc += kf.duration_ms
        return _fit_pixels(kfs[-1].pixels, count)


def _fit_pixels(pixels: list[RGB], count: int) -> list[RGB]:
    if len(pixels) == count:
        return list(pixels)
    if len(pixels) > count:
        return pixels[:count]
    return pixels + [(0, 0, 0)] * (count - len(pixels))


_EFFECT_CLASSES: list[type[HostEffect]] = [
    RainbowEffect,
    RotatingRainbowEffect,
    ColorChaseEffect,
    CometEffect,
    MeteorEffect,
    TwinkleEffect,
    SparkleEffect,
    FireEffect,
    ThermalFlameEffect,
    SnowfallEffect,
    WavesEffect,
    PulseEffect,
    AlternatingEffect,
    TheaterChaseEffect,
    ColorWipeEffect,
    RandomPixelsEffect,
    CandyCaneEffect,
    HollyEffect,
    FrostyEffect,
    PoliceSirenEffect,
    ThunderstormEffect,
    PlasmaEffect,
    GravityBounceEffect,
    Fireplace2DEffect,
    ColorSwirlEffect,
    CosmicAuroraEffect,
    LayeredPineHearthEffect,
    ClockSweepRadarEffect,
    DualRingSpinEffect,
    PolarSpiralVortexEffect,
    NorthernLights3DEffect,
    Candle3DEffect,
    ConvectionFire3DEffect,
    PendulumShockwave3DEffect,
    QuantumInterference3DEffect,
    JacobsLadder3DEffect,
    BlackHoleAccretion3DEffect,
    BioluminescentReef3DEffect,
    FireflyFlight3DEffect,
    FireflySwarm3DEffect,
    RipplePond3DEffect,
    HeartbeatCardiac3DEffect,
    DNAHelix3DEffect,
]

HOST_EFFECT_CATALOG: dict[str, type[HostEffect]] = {cls.info.id: cls for cls in _EFFECT_CLASSES}


def list_host_effects() -> list[EffectInfo]:
    """Return metadata for all built-in host per-pixel effects."""
    return [cls.info for cls in _EFFECT_CLASSES]


def create_host_effect(name: str, *, speed: float | None = None, **params: Any) -> HostEffect:
    """Instantiate a built-in host effect by ID or friendly alias."""
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "sparkling": "sparkle",
        "white_sparkle": "sparkle",
        "candycane": "candy_cane",
        "siren": "police",
        "thermal_flame_adv": "thermal_flame",
    }
    key = aliases.get(key, key)
    if key not in HOST_EFFECT_CATALOG:
        raise ValidationError(
            f"Unknown host effect {name!r}. Available: {', '.join(sorted(HOST_EFFECT_CATALOG))}"
        )
    cls = HOST_EFFECT_CATALOG[key]
    eff_speed = cls.info.default_speed if speed is None else speed
    return cls(speed=eff_speed, **params)
