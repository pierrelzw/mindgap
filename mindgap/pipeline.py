"""One day, end to end: extract -> gate -> analyze -> verify -> link -> render -> notify."""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import paths
from .analyze import analyze_day
from .config import Config, MindgapError
from .extract import extract_day, snapshot_history
from .link import link_evidence
from .log import get_logger
from .notify import notify_failure, notify_insufficient, notify_ok
from .render import ingest, render_all
from .verify import summary, verify_evidence


@dataclass
class RunResult:
    day: str
    status: str  # ok | insufficient | failed
    stage: str = ""
    error: str = ""
    html: Path | None = None
    cost_usd: float = 0.0
    secs: float = 0.0


def today_local(cfg: Config) -> date:
    return datetime.now(cfg.tz).date()


def run_day(day: date, cfg: Config, *, catchup: bool = False, notify: bool = True, force: bool = False) -> RunResult:
    ds = day.isoformat()
    if day >= today_local(cfg) and not force:
        raise MindgapError(f"{ds} 还没结束（{cfg.timezone} 今天是 {today_local(cfg)}），加 --force 才会跑")
    work = paths.work_dir(cfg, ds)
    work.mkdir(parents=True, exist_ok=True)
    log = get_logger(cfg, day=ds)
    t0 = time.time()
    stage = "init"
    res = RunResult(day=ds, status="failed")
    try:
        stage = "extract"
        snap = snapshot_history(cfg.history, work / "history-snapshot.jsonl")
        prompts = extract_day(day, cfg, snap)
        (work / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
        n = len(prompts["prompts"])
        log.info("%s: %d prompts, %d sessions", ds, n, prompts["session_count"])

        if n < cfg.min_prompts:
            stage = "render"
            ingest(ds, work, cfg, "insufficient", None, None, None, {"catchup": catchup, "secs": 0, "cost_usd": 0})
            res.html = paths.day_html(cfg, ds)
            render_all(cfg)
            res.status = "insufficient"
            if notify:
                notify_insufficient(cfg, ds, n, res.html, log)
        else:
            stage = "analyze"
            analysis, run = analyze_day(ds, cfg, work, prompts, log)
            stage = "verify"
            ver = verify_evidence(analysis, prompts["prompts"], cfg.tz)
            (work / "verify.json").write_text(json.dumps(ver, ensure_ascii=False, indent=2), encoding="utf-8")
            stage = "link"
            links = link_evidence(analysis, prompts["prompts"], ver, cfg, log)
            (work / "links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
            stage = "render"
            run["catchup"] = catchup
            ingest(ds, work, cfg, "ok", analysis, ver, links, run)
            render_all(cfg)
            res.html = paths.day_html(cfg, ds)
            res.status, res.cost_usd = "ok", run.get("cost_usd") or 0.0
            log.info("%s: ok, evidence verified %d/%d, $%.3f -> %s", ds, *summary(ver), res.cost_usd, res.html)
            stage = "notify"
            if notify:
                notify_ok(cfg, ds, analysis, res.html, log)
    except Exception as ex:  # noqa: BLE001 - every failure must become a notification, not a crash
        res.status, res.stage, res.error = "failed", stage, f"{type(ex).__name__}: {ex}"
        log.error("%s: 失败于 %s\n%s", ds, stage, traceback.format_exc())
        if notify:
            notify_failure(cfg, ds, stage, work / "run.log", log)
    res.secs = round(time.time() - t0, 1)
    runs = paths.runs_file(cfg)
    runs.parent.mkdir(parents=True, exist_ok=True)
    with runs.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": ds, "started": datetime.fromtimestamp(t0).astimezone().isoformat(timespec="seconds"),
                             "status": res.status, "stage": res.stage, "error": res.error, "catchup": catchup,
                             "cost_usd": res.cost_usd, "duration_s": res.secs}, ensure_ascii=False) + "\n")
    return res
