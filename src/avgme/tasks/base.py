from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..bot import Bot
from ..humanize import jitter_interval

log = logging.getLogger(__name__)


@dataclass
class TaskResult:
    ok: bool
    detail: str = ""
    actions: int = 0


class Task(ABC):
    """One repeating game chore.

    Subclasses implement `run`; scheduling, jitter and the return-to-home
    guarantee are handled by the runner.
    """

    key: str = ""

    def __init__(self, config: dict, humanize: dict) -> None:
        self.config = config
        self.interval = float(config.get("interval_seconds", 600))
        self._jitter = humanize.get("interval_jitter", 0.15)
        self._next_run = 0.0  # 0 means "due immediately on startup"

    def is_due(self) -> bool:
        return time.monotonic() >= self._next_run

    def schedule_next(self) -> float:
        delay = jitter_interval(self.interval, self._jitter)
        self._next_run = time.monotonic() + delay
        return delay

    def seconds_until_due(self) -> float:
        return max(0.0, self._next_run - time.monotonic())

    @abstractmethod
    def run(self, bot: Bot) -> TaskResult:
        """Do the chore. The bot is already on the home screen."""
