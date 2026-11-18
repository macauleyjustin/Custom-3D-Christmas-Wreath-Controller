"""Non-blocking background FrameScheduler capped to verified hardware limits."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from controller.effects.base import HostEffect
from controller.exceptions import ValidationError
from controller.pixels.color import RGB
from controller.protocol.constants import DEFAULT_STREAM_FPS, HARD_MAX_FPS


@dataclass(frozen=True)
class SchedulerStats:
    """Telemetry reported by :class:`FrameScheduler`."""

    running: bool
    effect_id: str | None
    effect_name: str | None
    speed: float | None
    target_fps: float
    actual_fps: float
    frames_sent: int
    frames_dropped: int
    last_error: str | None


class FrameScheduler:
    """Background animation loop rendering a :class:`HostEffect` into frame submissions."""

    def __init__(
        self,
        submit_frame: Callable[[list[RGB]], None],
        *,
        led_count: int,
        target_fps: float = DEFAULT_STREAM_FPS,
    ) -> None:
        self._submit_frame = submit_frame
        self._led_count = led_count
        self._target_fps = self._validate_fps(target_fps)

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._effect: HostEffect | None = None
        self._frames_sent = 0
        self._frames_dropped = 0
        self._actual_fps = 0.0
        self._last_error: str | None = None

    @staticmethod
    def _validate_fps(fps: float) -> float:
        if isinstance(fps, bool) or not isinstance(fps, (int, float)):
            raise ValidationError(f"fps must be a number, got {fps!r}")
        val = float(fps)
        if not 1.0 <= val <= HARD_MAX_FPS:
            raise ValidationError(
                f"target_fps must be between 1.0 and {HARD_MAX_FPS} FPS (verified BL602 TCP ceiling)"
            )
        return val

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set()

    def set_target_fps(self, fps: float) -> None:
        val = self._validate_fps(fps)
        with self._lock:
            self._target_fps = val

    def set_speed(self, speed: float) -> None:
        with self._lock:
            if self._effect is None:
                raise ValidationError("No host effect is currently running")
            self._effect.set_speed(speed)

    def start(self, effect: HostEffect, *, target_fps: float | None = None) -> None:
        if target_fps is not None:
            self._target_fps = self._validate_fps(target_fps)
        self.stop()
        with self._lock:
            self._effect = effect
            self._frames_sent = 0
            self._frames_dropped = 0
            self._actual_fps = 0.0
            self._last_error = None
            self._stop_event.clear()
            t = threading.Thread(
                target=self._run_loop,
                args=(effect,),
                name=f"FrameScheduler-{effect.info.id}",
                daemon=True,
            )
            self._thread = t
            t.start()

    def stop(self) -> None:
        with self._lock:
            t = self._thread
            self._stop_event.set()
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        with self._lock:
            self._thread = None
            self._effect = None
            self._actual_fps = 0.0

    def _run_loop(self, effect: HostEffect) -> None:
        t0 = time.monotonic()
        frame_idx = 0
        fps_window_t = t0
        fps_window_count = 0

        while not self._stop_event.is_set():
            tick_start = time.monotonic()
            with self._lock:
                fps = self._target_fps
            period = 1.0 / fps

            try:
                pixels = effect.render(self._led_count, tick_start - t0, frame_idx)
                self._submit_frame(pixels)
                frame_idx += 1
                fps_window_count += 1
                now = time.monotonic()
                with self._lock:
                    self._frames_sent += 1
                    self._last_error = None
                    if now - fps_window_t >= 0.5:
                        self._actual_fps = round(fps_window_count / (now - fps_window_t), 1)
                        fps_window_t = now
                        fps_window_count = 0
            except Exception as exc:
                with self._lock:
                    self._frames_dropped += 1
                    self._last_error = str(exc)
                # Back off gently on transport error without busy-spinning
                if self._stop_event.wait(0.25):
                    break
                continue

            elapsed = time.monotonic() - tick_start
            sleep_for = period - elapsed
            if sleep_for > 0:
                if self._stop_event.wait(sleep_for):
                    break
            else:
                # Frame render/send took longer than target period; note drop if >2x period
                if elapsed > period * 1.8:
                    with self._lock:
                        self._frames_dropped += 1

    def stats(self) -> SchedulerStats:
        with self._lock:
            eff = self._effect
            return SchedulerStats(
                running=self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set(),
                effect_id=eff.info.id if eff else None,
                effect_name=eff.info.name if eff else None,
                speed=eff.speed if eff else None,
                target_fps=self._target_fps,
                actual_fps=self._actual_fps,
                frames_sent=self._frames_sent,
                frames_dropped=self._frames_dropped,
                last_error=self._last_error,
            )
