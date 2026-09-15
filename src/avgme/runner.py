"""The scheduling loop.

Each pass: check the session window, find due tasks, prove we're on the home
screen, run them, reschedule. Recovering to home *between* tasks rather than
only at startup is what lets the bot run for hours - a popup that appears
during one task doesn't poison the next.
"""

from __future__ import annotations

import logging
import time

from .bot import Bot
from .humanize import Session
from .state import recover_to_home
from .tasks import REGISTRY, Task

log = logging.getLogger(__name__)

IDLE_POLL_SECONDS = 5.0


def build_tasks(config: dict, only: str | None = None) -> list[Task]:
    humanize = config.get("humanize", {})
    tasks: list[Task] = []

    for key, task_config in (config.get("tasks") or {}).items():
        if only and key != only:
            continue
        if not only and not task_config.get("enabled", True):
            log.info("task %s is disabled in config", key)
            continue

        task_class = REGISTRY.get(key)
        if task_class is None:
            log.warning("no task implementation registered for %r - skipping", key)
            continue

        tasks.append(task_class(task_config, humanize))

    if only and not tasks:
        raise ValueError(
            f"no task named {only!r}. Available: {', '.join(sorted(REGISTRY))}"
        )
    return tasks


def build_session(config: dict) -> Session:
    raw = config.get("humanize", {}).get("session", {})
    return Session(
        enabled=bool(raw.get("enabled", False)),
        active_minutes=tuple(raw.get("active_minutes", [40, 40])),
        idle_minutes=tuple(raw.get("idle_minutes", [15, 15])),
    )


def run_once(bot: Bot, tasks: list[Task]) -> int:
    """Run every task a single time, in order. Returns the action count."""
    actions = 0
    for task in tasks:
        actions += _run_task(bot, task)
    return actions


def run_forever(bot: Bot, tasks: list[Task], config: dict) -> None:
    session = build_session(config)
    log.info("running tasks: %s", ", ".join(t.key for t in tasks))

    while True:
        if not session.is_active():
            wait = session.seconds_until_active()
            log.info("session idle for %.1f more minutes", wait / 60)
            time.sleep(min(wait, 60.0))
            continue

        due = [task for task in tasks if task.is_due()]
        if not due:
            soonest = min(task.seconds_until_due() for task in tasks)
            time.sleep(min(soonest, IDLE_POLL_SECONDS))
            continue

        for task in due:
            _run_task(bot, task)
            delay = task.schedule_next()
            log.info("next %s in %.1f min", task.key, delay / 60)


def _run_task(bot: Bot, task: Task) -> int:
    if not recover_to_home(bot):
        log.error("skipping %s - not on the home screen", task.key)
        return 0

    log.info("--- %s ---", task.key)
    try:
        result = task.run(bot)
    except Exception:
        # One task blowing up must not take the loop down; the next cycle
        # starts with a fresh recover_to_home anyway.
        log.exception("task %s raised", task.key)
        bot.dump(f"{task.key}-exception")
        return 0

    level = logging.INFO if result.ok else logging.WARNING
    log.log(level, "%s: %s", task.key, result.detail)
    return result.actions
