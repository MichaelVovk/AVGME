from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_CONFIG = Path("config/tasks.yaml")


def load_config(path: Path | None = None) -> dict:
    path = path or DEFAULT_CONFIG
    if not path.exists():
        raise FileNotFoundError(
            f"config not found at {path}. Copy config/tasks.yaml from the repo, "
            "or pass --config."
        )
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def humanize_section(config: dict) -> dict:
    section = dict(config.get("humanize", {}))
    session = dict(section.get("session", {}))
    section["session"] = session
    return section
