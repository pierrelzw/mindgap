"""Extract the prompts a human typed into Claude Code on one New York calendar day.

Source: ~/.claude/history.jsonl (one row per submitted prompt).
Filters: slash commands dropped, `[Pasted text #N +M lines]` placeholders stripped,
prompts longer than `long_prompt_chars` dropped (assumed AI-polished), secrets redacted.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config

PASTE = re.compile(r"\[Pasted text #\d+(?: \+\d+ lines)?\]")
REDACTED = "[已脱敏]"

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b"),
]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(REDACTED, text)
    return text


def window(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight). On a DST-change day this is 23 or 25 hours."""
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    nxt = day + timedelta(days=1)
    return start, datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz)


def snapshot_history(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def extract_day(day: date, cfg: Config, history_path: Path | None = None) -> dict:
    tz = cfg.tz
    start, end = window(day, tz)
    s_epoch, e_epoch = start.timestamp(), end.timestamp()  # aware datetimes with the same tzinfo compare by wall clock; use epoch
    total = slash = pasted = empty = long_ = 0
    sessions: set = set()
    kept: list[dict] = []
    path = history_path or cfg.history
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
                ts_s = int(r["timestamp"]) / 1000
            except (ValueError, KeyError, TypeError):
                continue
            if not (s_epoch <= ts_s < e_epoch):
                continue
            if r.get("project") in cfg.exclude_projects:
                continue
            total += 1
            d = r.get("display") or ""
            if d.lstrip().startswith("/"):
                slash += 1
                continue
            if PASTE.search(d):
                pasted += 1
            d = PASTE.sub("", d).strip()
            if not d:
                empty += 1
                continue
            if len(d) > cfg.long_prompt_chars:
                long_ += 1
                continue
            sessions.add(r.get("sessionId"))
            kept.append({
                "time": datetime.fromtimestamp(ts_s, tz).isoformat(timespec="seconds"),
                "ts": ts_s,
                "project": r.get("project"),
                "sessionId": r.get("sessionId"),
                "text": redact(d),
            })
    kept.sort(key=lambda p: p["ts"])
    prompts = []
    for i, p in enumerate(kept, 1):
        p.pop("ts")
        prompts.append({"id": f"{day.isoformat()}-{i:03d}", **p})
    return {
        "date": day.isoformat(),
        "tz": cfg.timezone,
        "total_rows": total,
        "slash": slash,
        "with_paste_placeholder": pasted,
        "empty_after_strip": empty,
        "filtered_long": long_,
        "session_count": len(sessions),
        "prompts": prompts,
    }
