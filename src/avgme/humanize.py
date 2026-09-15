"""Timing and tap jitter.

Two reasons this exists. The practical one: instant, pixel-identical taps land
mid-animation and desync from the UI, so a little slop actually makes the bot
more reliable. The other: a perfectly periodic input stream is a trivial
signature. This goes no further than that - nothing here touches the game
client or interferes with any integrity check.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .vision import Match

MIN_DELAY = 0.15


def jitter_point(match: Match, box_ratio: float = 0.6) -> tuple[int, int]:
    """A random point inside the central `box_ratio` of a matched box."""
    cx, cy = match.center
    span_x = max(1, int(match.w * box_ratio / 2))
    span_y = max(1, int(match.h * box_ratio / 2))
    return cx + random.randint(-span_x, span_x), cy + random.randint(-span_y, span_y)


def gaussian_delay(mean: float, stddev: float) -> float:
    return max(MIN_DELAY, random.gauss(mean, stddev))


def sleep(mean: float, stddev: float) -> None:
    time.sleep(gaussian_delay(mean, stddev))


def jitter_interval(seconds: float, spread: float) -> float:
    """Scatter a configured interval so it never repeats to the second."""
    return max(1.0, seconds * random.uniform(1 - spread, 1 + spread))


@dataclass
class Session:
    """Alternates active and idle stretches so the bot isn't running 24/7."""

    enabled: bool
    active_minutes: tuple[float, float]
    idle_minutes: tuple[float, float]
    _phase_ends_at: float = 0.0
    _active: bool = True

    def _roll(self, bounds: tuple[float, float]) -> float:
        return random.uniform(*bounds) * 60

    def is_active(self) -> bool:
        """True while the bot should be working; flips phase when one expires."""
        if not self.enabled:
            return True

        now = time.monotonic()
        if self._phase_ends_at == 0.0:
            self._phase_ends_at = now + self._roll(self.active_minutes)
            self._active = True
        elif now >= self._phase_ends_at:
            self._active = not self._active
            bounds = self.active_minutes if self._active else self.idle_minutes
            self._phase_ends_at = now + self._roll(bounds)

        return self._active

    def seconds_until_active(self) -> float:
        if not self.enabled or self._active:
            return 0.0
        return max(0.0, self._phase_ends_at - time.monotonic())
