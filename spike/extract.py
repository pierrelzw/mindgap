import json, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parent.parent))
from mindgap.extract import redact  # reuse redaction

DAY, TZ = (sys.argv[1] if len(sys.argv) > 1 else "2026-10-15"), ZoneInfo("America/New_York")
start = datetime.fromisoformat(DAY).replace(tzinfo=TZ); end = start + timedelta(days=1)
PASTE = re.compile(r"\[Pasted text #\d+(?: \+\d+ lines)?\]")
total = slash = pasted = empty = long_ = 0
sessions, prompts = set(), []
for line in (Path.home()/".claude/history.jsonl").open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    ts = datetime.fromtimestamp(int(r["timestamp"])/1000, TZ)
    if not (start <= ts < end): continue
    total += 1
    d = r.get("display", "")
    if d.lstrip().startswith("/"): slash += 1; continue
    if PASTE.search(d): pasted += 1
    d = PASTE.sub("", d).strip()
    if not d: empty += 1; continue
    if len(d) > 400: long_ += 1; continue
    sessions.add(r.get("sessionId"))
    prompts.append({"time": ts.isoformat(timespec="seconds"), "project": r.get("project"),
                    "sessionId": r.get("sessionId"), "text": redact(d)})
out = {"date": DAY, "total_rows": total, "slash": slash, "with_paste_placeholder": pasted,
       "empty_after_strip": empty, "filtered_long": long_, "session_count": len(sessions), "prompts": prompts}
D = Path(__file__).parent/"out/days"/DAY; D.mkdir(parents=True, exist_ok=True)
(D/"prompts.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print({k: v for k, v in out.items() if k != "prompts"}, "kept:", len(prompts), "chars:", sum(len(p["text"]) for p in prompts))
