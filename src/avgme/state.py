"""Knowing where we are, and getting back to the base screen.

This is the part that separates a bot from a recorded macro. Event ads,
level-up dialogs, daily-login popups and alliance invites appear unprompted; a
coordinate macro taps straight through them into whatever happens to be
underneath. Every task here starts by proving it's on the home screen.
"""

from __future__ import annotations

import logging
import time

from .bot import Bot

log = logging.getLogger(__name__)

HOME_ANCHORS = "home/anchor"
CLOSE_BUTTONS = "common/close"


def at_home(bot: Bot, *, fresh: bool = True) -> bool:
    """True when any home-screen anchor template is visible."""
    return bool(bot.find_prefix(HOME_ANCHORS, fresh=fresh, limit=1))


def dismiss_popups(bot: Bot, *, max_attempts: int | None = None) -> bool:
    """Close whatever is covering the screen. True if we reached home.

    Prefers a real close button when one is visible, since Back can exit the
    game from the base screen; falls back to Back for screens that have no X.
    """
    recovery = bot.config.get("recovery", {})
    attempts = max_attempts or recovery.get("max_attempts", 6)
    settle = recovery.get("settle_seconds", 1.2)

    for attempt in range(1, attempts + 1):
        if at_home(bot, fresh=True):
            return True

        close = bot.find_prefix(CLOSE_BUTTONS, limit=1)
        if close:
            log.info("dismissing popup via %s (attempt %d/%d)", close[0].template, attempt, attempts)
            bot.tap(close[0])
        else:
            log.info("no close button visible, pressing Back (attempt %d/%d)", attempt, attempts)
            bot.back()

        time.sleep(settle)

    return at_home(bot, fresh=True)


def recover_to_home(bot: Bot) -> bool:
    """Ensure the game is sitting on the base screen before a task runs."""
    if at_home(bot, fresh=True):
        return True

    log.info("not on the home screen - recovering")
    if dismiss_popups(bot):
        log.info("recovered to home")
        return True

    log.warning("could not get back to the home screen")
    bot.dump("recovery-failed")
    return False
