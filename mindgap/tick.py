"""The launchd entry point: decide which days are due, run them once each, remember what was done.

launchd calls `python3 -m mindgap tick` every 60 s. Everything is computed in the configured
timezone (America/New_York), never the machine's (Asia/Shanghai), so the 2026-11-01 DST change is safe.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from datetime import date, datetime, timedelta

from . import paths
from .config import Config, MindgapError
from .log import get_logger


def due_trigger(now_tz: datetime, hour: int, minute: int) -> date:
    """Date of the most recent (hour:minute) wall-clock instant that is <= now, in now's timezone."""
    d = now_tz.date()
    t = datetime(d.year, d.month, d.day, hour, minute, tzinfo=now_tz.tzinfo)  # tzinfo recomputes the UTC offset
    return d if now_tz.timestamp() >= t.timestamp() else d - timedelta(days=1)


def pending_triggers(last_done: date, due: date, catchup_days: int) -> list[date]:
    start = max(last_done + timedelta(days=1), due - timedelta(days=catchup_days - 1))
    return [start + timedelta(days=k) for k in range((due - start).days + 1)] if start <= due else []


def load_state(p) -> dict:
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(st, dict):
            st.setdefault("last_trigger_done", None)
            st.setdefault("days", {})
            return st
    except (OSError, ValueError):
        pass
    return {"last_trigger_done": None, "days": {}}


def save_state(p, st: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


@contextlib.contextmanager
def locked(cfg: Config):
    """Non-blocking exclusive lock; yields False if someone else holds it."""
    p = paths.lock_file(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = open(p, "w")
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        fh.close()


def record(st: dict, day: str, res, now: datetime) -> dict:
    rec = st["days"].setdefault(day, {"attempts": 0})
    rec.update(status=res.status, error=res.error, stage=res.stage, finished=now.isoformat(timespec="seconds"))
    return rec


def tick(cfg: Config, now: datetime | None = None, dry_run: bool = False, run_fn=None) -> int:
    from . import pipeline  # late import keeps `tick` testable without side effects
    run_fn = run_fn or pipeline.run_day
    log = get_logger(cfg, console=False)
    now = now or datetime.now(cfg.tz)
    sf = paths.state_file(cfg)
    with locked(cfg) as got:
        if not got:
            log.info("另一次运行进行中，退出")
            return 0
        due = due_trigger(now, cfg.hour, cfg.minute)
        st = load_state(sf)
        last = date.fromisoformat(st["last_trigger_done"]) if st["last_trigger_done"] else due - timedelta(days=1)

        def advance(t: date):
            cur = st["last_trigger_done"]
            if cur is None or t > date.fromisoformat(cur):
                st["last_trigger_done"] = t.isoformat()
            save_state(sf, st)

        todo = pending_triggers(last, due, cfg.catchup_days)
        if not todo:
            log.debug("无待办（最近到期触发 %s）", due)
            return 0
        for t in todo:
            day = t + timedelta(days=cfg.day_offset)
            ds = day.isoformat()
            rec = st["days"].get(ds, {"attempts": 0})
            if rec.get("status") in ("ok", "insufficient"):
                advance(t)
                continue
            if rec.get("attempts", 0) >= cfg.max_attempts:
                log.error("%s 已失败 %d 次，放弃（手动: python3 -m mindgap run --day %s）", ds, rec["attempts"], ds)
                advance(t)
                continue
            la = rec.get("last_attempt")
            if la and now - datetime.fromisoformat(la) < timedelta(minutes=cfg.retry_cooldown_min):
                log.info("%s 冷却中，稍后再试", ds)
                break
            if dry_run:
                print(f"trigger {t} -> analyze {ds}" + (" (catch-up)" if t != due else ""))
                continue
            rec = st["days"].setdefault(ds, {"attempts": 0})
            rec["attempts"] = rec.get("attempts", 0) + 1
            rec["last_attempt"] = now.isoformat(timespec="seconds")
            save_state(sf, st)
            log.info("运行 %s（触发 %s，第 %d 次）", ds, t, rec["attempts"])
            try:
                res = run_fn(day, cfg, catchup=(t != due))
            except MindgapError as e:
                from .pipeline import RunResult
                res = RunResult(day=ds, status="failed", stage="start", error=str(e))
            record(st, ds, res, datetime.now(cfg.tz))
            save_state(sf, st)
            if res.status == "failed":
                break
            advance(t)
    return 0
