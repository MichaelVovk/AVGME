"""A stand-in emulator.

Lets the task logic be tested end to end - taps, re-screencapping, recovery -
without the game running. The screen is a list of sprites; tapping one inside a
badge's box removes it, the way collecting does in the real game.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from conftest import paste


@dataclass
class Element:
    name: str
    patch: np.ndarray
    x: int
    y: int

    def contains(self, x: int, y: int) -> bool:
        h, w = self.patch.shape[:2]
        return self.x <= x < self.x + w and self.y <= y < self.y + h


@dataclass
class FakeAdb:
    background: np.ndarray
    elements: list[Element] = field(default_factory=list)
    taps: list[tuple[int, int]] = field(default_factory=list)
    back_presses: int = 0
    on_tap: object = None

    serial: str = "fake:5555"

    def connect(self) -> None:
        pass

    def resolution(self) -> tuple[int, int]:
        h, w = self.background.shape[:2]
        return w, h

    def screencap(self) -> np.ndarray:
        screen = self.background.copy()
        for element in self.elements:
            paste(screen, element.patch, element.x, element.y)
        return screen

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))
        hit = next((e for e in self.elements if e.contains(x, y)), None)
        if hit is None:
            return
        if self.on_tap is not None:
            self.on_tap(self, hit)
        else:
            self.elements.remove(hit)

    def back(self) -> None:
        self.back_presses += 1

    def swipe(self, *args, **kwargs) -> None:
        pass
