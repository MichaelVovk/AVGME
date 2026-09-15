"""The object tasks are handed: screen in, taps out.

Wrapping adb + templates + jitter here keeps each task file down to game logic
rather than plumbing, and gives dry-run a single place to intercept every tap.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .adb import Adb
from .humanize import jitter_point, sleep
from .vision import Match, Template, annotate, find, find_all, find_first

log = logging.getLogger(__name__)


class Bot:
    def __init__(
        self,
        adb: Adb,
        templates: dict[str, Template],
        config: dict,
        *,
        dry_run: bool = False,
        debug_dir: Path | None = None,
    ) -> None:
        self.adb = adb
        self.templates = templates
        self.config = config
        self.dry_run = dry_run
        self.debug_dir = debug_dir or Path("debug")
        self._humanize = config.get("humanize", {})
        self._screen: np.ndarray | None = None
        self._dry_run_matches: list[Match] = []

    # -- screen -----------------------------------------------------------

    def refresh(self) -> np.ndarray:
        """Grab a fresh frame and cache it as the current screen."""
        self._screen = self.adb.screencap()
        return self._screen

    @property
    def screen(self) -> np.ndarray:
        if self._screen is None:
            return self.refresh()
        return self._screen

    # -- lookups ----------------------------------------------------------

    def template(self, name: str) -> Template | None:
        template = self.templates.get(name)
        if template is None:
            log.debug("template %r is not loaded", name)
        return template

    def find(self, name: str, *, fresh: bool = False) -> Match | None:
        template = self.template(name)
        if template is None:
            return None
        screen = self.refresh() if fresh else self.screen
        return find(screen, template)

    def find_all(self, name: str, *, fresh: bool = False, limit: int = 20) -> list[Match]:
        template = self.template(name)
        if template is None:
            return []
        screen = self.refresh() if fresh else self.screen
        return find_all(screen, template, limit=limit)

    def find_any(self, names: list[str], *, fresh: bool = False) -> Match | None:
        screen = self.refresh() if fresh else self.screen
        return find_first(screen, self.templates, names)

    def find_prefix(self, prefix: str, *, fresh: bool = False, limit: int = 20) -> list[Match]:
        """Every match for all templates whose key starts with `prefix`.

        Lets a task say "tap all home/collect_* badges" without the task knowing
        how many kinds of badge exist - adding one is dropping in a PNG.
        """
        screen = self.refresh() if fresh else self.screen
        matches: list[Match] = []
        for key, template in self.templates.items():
            if key.startswith(prefix):
                matches.extend(find_all(screen, template, limit=limit))
        return sorted(matches, key=lambda m: m.score, reverse=True)

    def wait_for(
        self, names: list[str], *, timeout: float = 12.0, poll: float = 0.6
    ) -> Match | None:
        """Poll until one of `names` appears, or give up."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            match = self.find_any(names, fresh=True)
            if match:
                return match
            time.sleep(poll)
        log.debug("timed out waiting for any of %s", names)
        return None

    # -- input ------------------------------------------------------------

    def tap(self, match: Match) -> None:
        """Tap a matched element, with jitter, or record it in dry-run."""
        x, y = jitter_point(match, self._humanize.get("tap_box_ratio", 0.6))

        if self.dry_run:
            log.info("[dry-run] would tap %s (%.2f) at (%d, %d)", match.template, match.score, x, y)
            self._dry_run_matches.append(match)
            return

        log.info("tap %s (%.2f) at (%d, %d)", match.template, match.score, x, y)
        self.adb.tap(x, y)
        self.pause()

    def back(self) -> None:
        if self.dry_run:
            log.info("[dry-run] would press Back")
            return
        log.debug("press Back")
        self.adb.back()
        self.pause()

    def pause(self) -> None:
        mean, stddev = self._humanize.get("tap_delay", [0.55, 0.18])
        sleep(mean, stddev)

    # -- debugging --------------------------------------------------------

    def dump(self, label: str, matches: list[Match] | None = None) -> Path:
        """Save an annotated screenshot. The first thing to look at when a
        cycle misbehaves: it shows exactly what the bot saw and matched."""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.debug_dir / f"{stamp}-{label}.png"
        cv2.imwrite(str(path), annotate(self.screen, matches or []))
        log.info("wrote %s", path)
        return path

    def take_dry_run_matches(self) -> list[Match]:
        matches, self._dry_run_matches = self._dry_run_matches, []
        return matches
