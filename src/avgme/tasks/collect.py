"""Tap the production badges that pop over shelter buildings.

The one rule that matters: re-screencap between taps. Collecting a badge plays
an animation, can shift the ones behind it, and occasionally spawns a new one -
so a single find_all() followed by a burst of taps at stale coordinates is
exactly the bug this design exists to avoid.
"""

from __future__ import annotations

import logging

from ..bot import Bot
from ..state import at_home
from .base import Task, TaskResult

log = logging.getLogger(__name__)

BADGE_PREFIX = "home/collect"


class CollectTask(Task):
    key = "collect"

    def run(self, bot: Bot) -> TaskResult:
        cap = int(self.config.get("max_taps_per_cycle", 25))
        collected = 0

        while collected < cap:
            badges = bot.find_prefix(BADGE_PREFIX, fresh=True, limit=cap)
            if not badges:
                break

            # One tap per pass, then look again - the screen has changed.
            bot.tap(badges[0])
            collected += 1

            if not at_home(bot, fresh=True):
                # A collect can trigger a "storage full" or level-up dialog.
                log.info("left the home screen after collecting; stopping this cycle")
                break

        if collected >= cap:
            log.warning(
                "hit the %d-tap cap - a collect template may be matching something "
                "that never disappears. Check the latest debug screenshot.",
                cap,
            )
            bot.dump("collect-cap-hit", bot.find_prefix(BADGE_PREFIX))

        detail = f"collected {collected}" if collected else "nothing ready"
        return TaskResult(ok=True, detail=detail, actions=collected)
