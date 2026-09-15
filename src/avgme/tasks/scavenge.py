"""Claim finished scavenge runs and send the empty slots back out.

Driven entirely by *state templates* rather than slot positions: whatever the
screen is showing - a claimable run, an idle slot, a confirm dialog - decides
the next tap. That makes partial completion, a mid-run popup, or a different
number of unlocked slots all non-events, where a positional macro would need a
branch for each.
"""

from __future__ import annotations

import logging

from ..bot import Bot
from ..state import dismiss_popups
from .base import Task, TaskResult

log = logging.getLogger(__name__)

ENTRY = ["home/scavenge_entry"]
SCREEN_ANCHOR = ["scavenge/anchor"]
CLAIM = ["scavenge/claim"]
DISPATCH = ["scavenge/dispatch"]
CONFIRM = ["scavenge/confirm"]


class ScavengeTask(Task):
    key = "scavenge"

    def run(self, bot: Bot) -> TaskResult:
        if not self._open(bot):
            return TaskResult(ok=False, detail="could not open the scavenge screen")

        claimed = self._claim_finished(bot)
        dispatched = self._fill_empty_slots(bot)

        self._leave(bot)

        parts = []
        if claimed:
            parts.append(f"claimed {claimed}")
        if dispatched:
            parts.append(f"dispatched {dispatched}")
        return TaskResult(
            ok=True,
            detail=", ".join(parts) or "nothing to do",
            actions=claimed + dispatched,
        )

    # -- navigation -------------------------------------------------------

    def _open(self, bot: Bot) -> bool:
        entry = bot.find_any(ENTRY, fresh=True)
        if entry is None:
            log.warning("scavenge entry point not found on the home screen")
            bot.dump("scavenge-entry-missing")
            return False

        bot.tap(entry)
        if bot.wait_for(SCREEN_ANCHOR) is None:
            log.warning("scavenge screen did not appear after tapping the entry point")
            bot.dump("scavenge-open-failed")
            return False
        return True

    def _leave(self, bot: Bot) -> None:
        if not dismiss_popups(bot):
            log.warning("could not return home after scavenging")

    # -- steps ------------------------------------------------------------

    def _claim_finished(self, bot: Bot) -> int:
        """Tap Claim until none is left, dismissing each reward popup."""
        claimed = 0
        for _ in range(int(self.config.get("max_slots", 6))):
            match = bot.find_any(CLAIM, fresh=True)
            if match is None:
                break

            bot.tap(match)
            claimed += 1

            # Rewards land in a popup that hides the rest of the list.
            if bot.wait_for(SCREEN_ANCHOR, timeout=6.0) is None:
                dismiss_popups(bot, max_attempts=3)
                if bot.wait_for(SCREEN_ANCHOR, timeout=6.0) is None:
                    log.info("lost the scavenge screen while claiming; stopping here")
                    break

        return claimed

    def _fill_empty_slots(self, bot: Bot) -> int:
        """Send out every slot that is showing Dispatch."""
        dispatched = 0
        for _ in range(int(self.config.get("max_slots", 6))):
            match = bot.find_any(DISPATCH, fresh=True)
            if match is None:
                break

            bot.tap(match)

            confirm = bot.wait_for(CONFIRM, timeout=8.0)
            if confirm is None:
                # Some slots dispatch without a confirmation step.
                log.debug("no confirm dialog appeared; assuming the run started")
            else:
                bot.tap(confirm)

            if bot.wait_for(SCREEN_ANCHOR, timeout=8.0) is None:
                dismiss_popups(bot, max_attempts=3)
                if bot.wait_for(SCREEN_ANCHOR, timeout=6.0) is None:
                    log.info("lost the scavenge screen while dispatching; stopping here")
                    dispatched += 1
                    break

            dispatched += 1

        return dispatched
