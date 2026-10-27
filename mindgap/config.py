"""Configuration: every tunable lives in <repo>/config.json."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, fields
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO / "config.json"


class MindgapError(RuntimeError):
    """A failure with a human-readable message (shown in the failure notification)."""


@dataclass
class Config:
    timezone: str = "America/New_York"
    hour: int = 18
    minute: int = 0
    day_offset: int = -1
    catchup_days: int = 7
    max_attempts: int = 3
    retry_cooldown_min: int = 60
    min_prompts: int = 8
    long_prompt_chars: int = 400
    model: str | None = None
    fallback_model: str | None = "sonnet"
    max_budget_usd: float = 3
    timeout_s: int = 900
    tools: str = ""
    archive_dir: str = "~/Documents/my_mindgap"
    history_path: str = "~/.claude/history.jsonl"
    projects_dir: str = "~/.claude/projects"
    claude_bin: str | None = None
    uvx_bin: str | None = None
    notifier_bin: str = "/opt/homebrew/bin/terminal-notifier"
    notify: bool = True
    exclude_projects: list = field(default_factory=list)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def archive(self) -> Path:
        return Path(self.archive_dir).expanduser()

    @property
    def history(self) -> Path:
        return Path(self.history_path).expanduser()

    @property
    def projects(self) -> Path:
        return Path(self.projects_dir).expanduser()


def load_config(path: Path | str | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    known = {f.name for f in fields(Config)}
    unknown = set(data) - known
    if unknown:
        raise MindgapError(f"config.json 有未知字段: {sorted(unknown)}")
    return Config(**data)


def resolve_bin(name: str, override: str | None) -> str:
    """Absolute path of an executable; `override` wins, else search PATH."""
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            return str(p)
        raise MindgapError(f"找不到 {name}: {override}")
    found = shutil.which(name)
    if not found:
        raise MindgapError(f"找不到 {name}（PATH 里没有）")
    return found
