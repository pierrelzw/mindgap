"""Archive layout (outside the repo)."""
from __future__ import annotations

from pathlib import Path

from .config import Config


def work_dir(cfg: Config, day: str) -> Path:
    return cfg.archive / "work" / day


def logs_dir(cfg: Config) -> Path:
    return cfg.archive / "logs"


def state_file(cfg: Config) -> Path:
    return cfg.archive / "state.json"


def lock_file(cfg: Config) -> Path:
    return cfg.archive / ".lock"


def runs_file(cfg: Config) -> Path:
    return cfg.archive / "runs.jsonl"


def day_json(cfg: Config, day: str) -> Path:
    return cfg.archive / day[:4] / day[5:7] / f"{day}.json"


def day_html(cfg: Config, day: str) -> Path:
    return cfg.archive / day[:4] / day[5:7] / f"{day}.html"


def transcripts_dir(cfg: Config) -> Path:
    return cfg.archive / "transcripts"
