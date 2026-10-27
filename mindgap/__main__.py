"""python3 -m mindgap tick | run | extract | render | state"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta

from . import paths
from .config import MindgapError, load_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mindgap", description=__doc__)
    ap.add_argument("--config", help="config.json path (default: <repo>/config.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tick", help="launchd entry: run whatever is due")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("run", help="analyze one day now")
    p.add_argument("--day", help="YYYY-MM-DD in the configured timezone (default: the configured day before today)")
    p.add_argument("--force", action="store_true", help="allow a day that has not finished yet")
    p.add_argument("--no-notify", action="store_true")
    p = sub.add_parser("extract", help="extract prompts for one day only (no LLM)")
    p.add_argument("--day", required=True)
    sub.add_parser("render", help="re-render every page and the index")
    sub.add_parser("state", help="print state.json")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    try:
        if a.cmd == "tick":
            from .tick import tick
            return tick(cfg, dry_run=a.dry_run)
        if a.cmd == "run":
            from . import pipeline
            from .tick import load_state, locked, record, save_state
            day = (date.fromisoformat(a.day) if a.day
                   else datetime.now(cfg.tz).date() + timedelta(days=cfg.day_offset))
            with locked(cfg) as got:
                if not got:
                    print("另一次运行进行中", file=sys.stderr)
                    return 1
                res = pipeline.run_day(day, cfg, notify=not a.no_notify, force=a.force)
                sf = paths.state_file(cfg)
                st = load_state(sf)
                rec = st["days"].setdefault(day.isoformat(), {"attempts": 0})
                rec["attempts"] = rec.get("attempts", 0) + 1
                rec["last_attempt"] = datetime.now(cfg.tz).isoformat(timespec="seconds")
                record(st, day.isoformat(), res, datetime.now(cfg.tz))
                save_state(sf, st)
            print(f"{res.day}: {res.status} {res.stage} {res.error} {res.html or ''} ${res.cost_usd:.3f} {res.secs}s")
            return 0 if res.status != "failed" else 2
        if a.cmd == "extract":
            from .extract import extract_day, snapshot_history
            d = date.fromisoformat(a.day)
            w = paths.work_dir(cfg, a.day)
            w.mkdir(parents=True, exist_ok=True)
            out = extract_day(d, cfg, snapshot_history(cfg.history, w / "history-snapshot.jsonl"))
            (w / "prompts.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print({k: v for k, v in out.items() if k != "prompts"}, "kept:", len(out["prompts"]))
            return 0
        if a.cmd == "render":
            from .render import render_all
            print(render_all(cfg))
            return 0
        if a.cmd == "state":
            from .tick import load_state
            print(json.dumps(load_state(paths.state_file(cfg)), ensure_ascii=False, indent=2))
            return 0
    except MindgapError as e:
        print(f"mindgap: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
