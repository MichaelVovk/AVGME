from .base import Task, TaskResult
from .collect import CollectTask
from .scavenge import ScavengeTask

#: Config key -> task class. Adding a task is adding a module and a line here.
REGISTRY: dict[str, type[Task]] = {
    "collect": CollectTask,
    "scavenge": ScavengeTask,
}

__all__ = ["Task", "TaskResult", "CollectTask", "ScavengeTask", "REGISTRY"]
