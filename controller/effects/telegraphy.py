"""Optical telegraphy generators (Morse Code & ASCII Binary) over WreathController."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from controller.exceptions import ValidationError
from controller.pixels.color import NAMED_COLORS, RGB

if TYPE_CHECKING:
    from controller.devices.wreath import WreathController

MORSE_CODE_DICT: dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....",
    "6": "-....", "7": "--...", "8": "---..", "9": "----.", "0": "-----",
    ",": "--..--", ".": ".-.-.-", "?": "..--..", "/": "-..-.", "-": "-....-",
    "(": "-.--.", ")": "-.--.-", " ": " ",
}


def encode_morse_timeline(text: str, wpm: float = 15.0) -> list[tuple[bool, float]]:
    """Compile ``text`` into a list of ``(is_on, duration_s)`` PARIS pulses."""
    wpm = max(1.0, min(50.0, float(wpm)))
    t_unit = 1.2 / wpm
    steps: list[tuple[bool, float]] = []
    for char in text.upper():
        if char == " ":
            steps.append((False, t_unit * 7.0))
            continue
        code = MORSE_CODE_DICT.get(char)
        if not code:
            continue
        for symbol in code:
            steps.append((True, t_unit * (1.0 if symbol == "." else 3.0)))
            steps.append((False, t_unit * 1.0))
        steps.append((False, t_unit * 3.0))
    return steps


def encode_binary_timeline(text: str, bps: float = 2.0) -> list[tuple[str, float]]:
    """Compile ``text`` into ``('1'|'0'|'GAP', duration_s)`` 8-bit ASCII frames."""
    bps = max(0.1, min(10.0, float(bps)))
    t_total = 1.0 / bps
    t_on = t_total * 0.8
    t_gap = t_total * 0.2
    bits = "".join(format(ord(ch), "08b") for ch in text)
    steps: list[tuple[str, float]] = []
    for bit in bits:
        steps.append((bit, t_on))
        steps.append(("GAP", t_gap))
    return steps


def _resolve_color(color: str | RGB) -> RGB:
    if isinstance(color, tuple) and len(color) == 3:
        return color
    key = str(color).upper()
    if key not in NAMED_COLORS:
        raise ValidationError(f"Unknown color name: {color!r}")
    return NAMED_COLORS[key]


def transmit_morse(
    ctrl: "WreathController",
    text: str,
    *,
    color: str | RGB = "GREEN",
    wpm: float = 15.0,
    loop: bool = False,
    stop_event: threading.Event | None = None,
) -> None:
    """Transmit ``text`` as Morse code on ``ctrl``."""
    on_rgb = _resolve_color(color)
    steps = encode_morse_timeline(text, wpm=wpm)
    if not steps:
        raise ValidationError("No Morse-encodable characters in text")
    ctrl.stop_effect()
    ctrl.power_on()
    while True:
        for state, dur in steps:
            if stop_event and stop_event.is_set():
                ctrl.set_color(0, 0, 0)
                return
            ctrl.set_color(*(on_rgb if state else (0, 0, 0)))
            time.sleep(dur)
        if not loop:
            ctrl.set_color(0, 0, 0)
            return
        time.sleep(1.2 / max(1.0, wpm) * 7.0)


def transmit_binary(
    ctrl: "WreathController",
    text: str,
    *,
    one_color: str | RGB = "BLUE",
    zero_color: str | RGB = "RED",
    bps: float = 2.0,
    loop: bool = False,
    stop_event: threading.Event | None = None,
) -> None:
    """Transmit ``text`` as 8-bit ASCII binary pulses on ``ctrl``."""
    c1 = _resolve_color(one_color)
    c0 = _resolve_color(zero_color)
    steps = encode_binary_timeline(text, bps=bps)
    if not steps:
        raise ValidationError("Text must not be empty")
    ctrl.stop_effect()
    ctrl.power_on()
    while True:
        for kind, dur in steps:
            if stop_event and stop_event.is_set():
                ctrl.set_color(0, 0, 0)
                return
            if kind == "1":
                ctrl.set_color(*c1)
            elif kind == "0":
                ctrl.set_color(*c0)
            else:
                ctrl.set_color(0, 0, 0)
            time.sleep(dur)
        if not loop:
            ctrl.set_color(0, 0, 0)
            return
        time.sleep(1.0)
