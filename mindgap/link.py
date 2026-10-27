"""Link each verified evidence quote to its message in a claude-code-transcripts page."""
from __future__ import annotations

import glob
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import paths
from .config import Config, MindgapError, resolve_bin
from .verify import norm, _SPLIT


def _frags(quote: str) -> list[str]:
    fs = [f for f in (norm(x) for x in _SPLIT.split(quote)) if len(f) >= 4]
    return fs or [norm(quote)]


def user_msgs(jsonl: Path) -> Iterator[tuple[str, str, bool]]:
    """(timestamp, text, queued). Compaction summaries quote old prompts, so they never count."""
    with open(jsonl, encoding="utf-8", errors="replace") as fh:
        for l in fh:
            try:
                r = json.loads(l)
            except ValueError:
                continue
            at = r.get("attachment") or {}
            if r.get("type") == "attachment" and at.get("type") == "queued_command":
                yield r["timestamp"], at.get("prompt", ""), True
                continue
            if r.get("type") == "queue-operation" and r.get("operation") == "remove":
                yield r["timestamp"], r.get("content", ""), True
                continue
            if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"):
                continue
            c = (r.get("message") or {}).get("content")
            t = c if isinstance(c, str) else "".join(b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text")
            if t.strip() and "timestamp" in r:
                yield r["timestamp"], t, False


def ensure_transcript(sid: str, jsonl: Path, out_dir: Path, uvx: str, log) -> bool:
    if (out_dir / "index.html").exists():
        return True
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    for extra in (["--offline"], []):
        try:
            r = subprocess.run([uvx, *extra, "claude-code-transcripts", "json", str(jsonl), "-o", str(out_dir)],
                               capture_output=True, text=True, timeout=180)
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("transcripts %s: %s", sid[:8], e)
            continue
        if r.returncode == 0 and (out_dir / "index.html").exists():
            return True
        log.warning("transcripts %s rc=%s %s", sid[:8], r.returncode, r.stderr.strip()[-200:])
    return False


def link_evidence(analysis: dict, prompts: list[dict], verify: list[dict], cfg: Config, log) -> list[dict]:
    try:
        uvx = resolve_bin("uvx", cfg.uvx_bin)
    except MindgapError as e:
        log.warning("%s; 跳过对话链接", e)
        uvx = None
    arc = cfg.archive
    out = []
    for ev, v in zip(analysis["evidence"], verify):
        rec = {"i": v["i"], "session": ev["sessionId"], "href": None, "msg_time": None, "delta_s": None, "queued": False, "in_session": False}
        idx = v.get("prompt_index")
        if idx is None or uvx is None:
            out.append(rec)
            continue
        p = prompts[idx]
        sid = p["sessionId"]
        rec["session"] = sid
        src = glob.glob(str(cfg.projects / "*" / f"{sid}.jsonl"))
        if not src:
            out.append(rec)
            continue
        try:
            tx = paths.transcripts_dir(cfg) / sid
            if not ensure_transcript(sid, Path(src[0]), tx, uvx, log):
                out.append(rec)
                continue
            fs = _frags(ev["quote"])
            t0 = datetime.fromisoformat(p["time"])
            msgs = list(user_msgs(Path(src[0])))
            hits = [(abs((datetime.fromisoformat(ts.replace("Z", "+00:00")) - t0).total_seconds()), ts)
                    for ts, t, _ in msgs if all(f in norm(t) for f in fs)]
            queued = {ts for ts, _, qd in msgs if qd}
            if hits:
                dt, ts = min(hits)
                anchor = "msg-" + ts.replace(":", "-").replace(".", "-")
                pages = sorted(tx.glob("page-*.html"))
                if ts in queued:  # queued prompts are not rendered; point at the first message after it
                    ids = sorted(i for f in pages for i in re.findall(r'id="(msg-[^"]+)"', f.read_text(encoding="utf-8")))
                    anchor = next((i for i in ids if i >= anchor), anchor)
                page = next((f.name for f in pages if f'id="{anchor}"' in f.read_text(encoding="utf-8")), None)
                rec.update(in_session=True, msg_time=ts, delta_s=round(dt, 1), queued=ts in queued,
                           href=f"transcripts/{sid}/{page}#{anchor}" if page else f"transcripts/{sid}/index.html")
            else:
                rec["href"] = f"transcripts/{sid}/index.html"
        except Exception as e:  # linking is best-effort; never fail the report over it
            log.warning("link evidence %d: %s", v["i"], e)
        out.append(rec)
    return out
