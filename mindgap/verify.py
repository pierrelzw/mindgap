"""Mechanical check that every evidence quote really is in the engineer's prompts.

The verdict comes only from string matching, never from the model.
Statuses: verified | partial | unverified. Nothing is ever deleted; the page shows failures in red.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

TIME_TOLERANCE_S = 60
_SPLIT = re.compile(r"…|\.\.\.|\[已脱敏\]")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def _parse_time(s: str, tz: ZoneInfo | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat((s or "").strip().replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    if dt.tzinfo is None:
        if tz is None:
            return None
        dt = dt.replace(tzinfo=tz)
    return dt


def _time_delta(ev_time: str, rec_time: str, tz) -> float | None:
    a, b = _parse_time(ev_time, tz), _parse_time(rec_time, tz)
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds())  # aware - aware subtracts as instants


def verify_evidence(analysis: dict, prompts: list[dict], tz: ZoneInfo | None = None) -> list[dict]:
    normed = [norm(p["text"]) for p in prompts]
    out = []
    for i, ev in enumerate(analysis.get("evidence", [])):
        q = norm(ev.get("quote", ""))
        sid = ev.get("sessionId")
        rec = {"i": i, "status": "unverified", "prompt_index": None, "session_ok": False,
               "time_ok": False, "delta_s": None, "note": ""}
        same = [k for k, p in enumerate(prompts) if p.get("sessionId") == sid]
        rec["session_ok"] = bool(same)
        exact = [k for k in same if q and q in normed[k]]
        frags = [f for f in (norm(x) for x in _SPLIT.split(ev.get("quote", ""))) if len(f) >= 4]
        frag_hit = [k for k in same if frags and all(f in normed[k] for f in frags)]
        cands = exact or frag_hit
        if cands:
            def delta(k):
                d = _time_delta(ev.get("time", ""), prompts[k]["time"], tz)
                return d if d is not None else 1e12
            best = min(cands, key=delta)
            d = _time_delta(ev.get("time", ""), prompts[best]["time"], tz)
            rec.update(prompt_index=best, delta_s=d, time_ok=d is not None and d <= TIME_TOLERANCE_S)
            if exact and rec["time_ok"]:
                rec["status"] = "verified"
            else:
                rec["status"] = "partial"
                rec["note"] = ("引文含省略号，分段命中同一条 prompt" if not exact else "") + \
                              ("；" if not exact and not rec["time_ok"] else "") + \
                              ("时间与原始记录不符" if not rec["time_ok"] else "")
        else:
            elsewhere = [k for k, t in enumerate(normed) if q and q in t]
            rec["note"] = ("原话存在，但属于另一个会话" if elsewhere else
                           ("会话 ID 不存在" if not same else "在该会话的 prompt 中找不到这句话"))
        out.append(rec)
    return out


def summary(verify: list[dict]) -> tuple[int, int]:
    return sum(1 for v in verify if v["status"] == "verified"), len(verify)


def problems(verify: list[dict]) -> list[str]:
    """Feedback lines for a retry."""
    msgs = []
    for v in verify:
        if v["status"] != "verified":
            msgs.append(f"evidence[{v['i']}] 核验失败（{v['status']}）：{v['note']}。"
                        "quote 必须是某条记录 text 的连续逐字子串，sessionId 与 time 必须从同一条记录原样复制。")
    return msgs
