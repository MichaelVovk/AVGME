"""Template matching - how the bot decides *where* to tap.

Fixed coordinates are what make recorded macros break the first time a popup
shifts the layout. Everything here finds a button by its appearance instead, so
the bot is tolerant of anything that doesn't change the button itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Template:
    name: str
    image: np.ndarray
    threshold: float

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.image.shape[:2]
        return w, h


@dataclass(frozen=True)
class Match:
    template: str
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    @property
    def box(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h


def load_templates(directory: Path, threshold: float) -> dict[str, Template]:
    """Load every PNG under `directory` (recursively) keyed by `subdir/stem`.

    A template may carry its own threshold in its filename as `name@0.92.png`,
    which is handy for the rare button that needs a looser or stricter match than
    the global default.
    """
    templates: dict[str, Template] = {}
    if not directory.exists():
        return templates

    for path in sorted(directory.rglob("*.png")):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            log.warning("skipping unreadable template: %s", path)
            continue

        stem = path.stem
        own_threshold = threshold
        if "@" in stem:
            stem, _, raw = stem.rpartition("@")
            try:
                own_threshold = float(raw)
            except ValueError:
                stem = path.stem

        key = path.relative_to(directory).parent.as_posix()
        key = stem if key == "." else f"{key}/{stem}"
        templates[key] = Template(name=key, image=image, threshold=own_threshold)

    return templates


def find_all(
    screen: np.ndarray,
    template: Template,
    *,
    limit: int = 20,
    min_distance: float = 0.5,
) -> list[Match]:
    """All non-overlapping matches above the template's threshold, best first.

    `min_distance` is expressed as a fraction of the template size: two hits
    closer than that are treated as the same button seen twice.
    """
    th, tw = template.image.shape[:2]
    sh, sw = screen.shape[:2]
    if th > sh or tw > sw:
        log.warning("template %s (%dx%d) is larger than the screen", template.name, tw, th)
        return []

    heat = cv2.matchTemplate(screen, template.image, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(heat >= template.threshold)
    if len(xs) == 0:
        return []

    candidates = sorted(
        ((float(heat[y, x]), int(x), int(y)) for x, y in zip(xs, ys)),
        key=lambda c: c[0],
        reverse=True,
    )

    kept: list[Match] = []
    gap_x, gap_y = tw * min_distance, th * min_distance
    for score, x, y in candidates:
        if any(abs(x - m.x) < gap_x and abs(y - m.y) < gap_y for m in kept):
            continue
        kept.append(Match(template.name, x, y, tw, th, score))
        if len(kept) >= limit:
            break

    return kept


def find(screen: np.ndarray, template: Template) -> Match | None:
    """The single best match, or None."""
    matches = find_all(screen, template, limit=1)
    return matches[0] if matches else None


def find_first(
    screen: np.ndarray, templates: dict[str, Template], names: list[str]
) -> Match | None:
    """The best match across several templates - for 'any of these means X'."""
    best: Match | None = None
    for name in names:
        template = templates.get(name)
        if template is None:
            log.debug("template %r is not loaded", name)
            continue
        match = find(screen, template)
        if match and (best is None or match.score > best.score):
            best = match
    return best


def annotate(screen: np.ndarray, matches: list[Match]) -> np.ndarray:
    """Draw match boxes onto a copy of the screen, for dry-run inspection."""
    canvas = screen.copy()
    for match in matches:
        x, y, w, h = match.box
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            canvas,
            f"{match.template} {match.score:.2f}",
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return canvas
