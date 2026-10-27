import json, re, sys, subprocess, glob
from datetime import datetime
from pathlib import Path
# usage: link.py DAY — map each evidence quote to its message in a claude-code-transcripts HTML, and check it mechanically
H = Path(__file__).parent; D = H/"out/days"/sys.argv[1]; ARC = Path.home()/"Documents/my_mindgap"
UVX = "/Users/ai/.local/share/mise/installs/uv/latest/uv-aarch64-apple-darwin/uvx"
a = json.loads((D/"analysis.json").read_text()); p = json.loads((D/"prompts.json").read_text())
norm = lambda s: re.sub(r"\s+", "", s)
frags = lambda q: [f for f in (norm(x) for x in re.split(r"[·…]|\.\.\.|\[已脱敏\]", q)) if len(f) >= 4]

def user_msgs(f):  # (timestamp, text, queued); compaction summaries quote old prompts, so they never count
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        at = r.get("attachment") or {}
        if r.get("type") == "attachment" and at.get("type") == "queued_command":  # typed while the AI was mid-turn
            yield r["timestamp"], at.get("prompt", ""), True; continue
        if r.get("type") == "queue-operation" and r.get("operation") == "remove":  # delivery time = history.jsonl time
            yield r["timestamp"], r.get("content", ""), True; continue
        if r.get("type") != "user" or r.get("isMeta") or r.get("isCompactSummary"): continue
        c = r["message"]["content"]
        t = c if isinstance(c, str) else "".join(b.get("text", "") for b in c if b.get("type") == "text")
        if t.strip(): yield r["timestamp"], t, False

out = []
for ev in a["evidence"]:
    fs = frags(ev["quote"]); sid = ev["session"]
    in_input = all(any(f in norm(x["text"]) for x in p["prompts"] if x["sessionId"] == sid) for f in fs)
    src = glob.glob(str(Path.home()/f".claude/projects/*/{sid}.jsonl"))
    rec = {"session": sid, "in_input": in_input, "in_session": False, "href": None, "msg_time": None, "jsonl": src[0] if src else None}
    if src:
        t0 = datetime.fromisoformat(ev["time"])
        hits = [(abs((datetime.fromisoformat(ts.replace("Z", "+00:00")) - t0).total_seconds()), ts) for ts, t, qd in user_msgs(src[0]) if all(f in norm(t) for f in fs)]
        queued = {ts for ts, t, qd in user_msgs(src[0]) if qd}
        tx = ARC/"transcripts"/sid
        if not (tx/"index.html").exists():
            tx.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([UVX, "claude-code-transcripts", "json", src[0], "-o", str(tx)], check=True, capture_output=True)
        if hits:
            dt, ts = min(hits); anchor = "msg-" + ts.replace(":", "-").replace(".", "-")
            if ts in queued:  # claude-code-transcripts doesn't render queued prompts: point at the first message after it
                ids = sorted(i for f in tx.glob("page-*.html") for i in re.findall(r'id="(msg-[^"]+)"', f.read_text()))
                anchor = next((i for i in ids if i >= anchor), anchor)
            page = next((f.name for f in sorted(tx.glob("page-*.html")) if f'id="{anchor}"' in f.read_text()), None)
            rec.update(in_session=True, msg_time=ts, delta_s=round(dt, 1), time_ok=dt <= 60, queued=ts in queued,
                       href=f"transcripts/{sid}/{page}#{anchor}" if page else f"transcripts/{sid}/index.html")
        else:
            rec["href"] = f"transcripts/{sid}/index.html"
    out.append(rec); print(rec["in_input"], rec["in_session"], rec.get("delta_s"), rec["href"])
(D/"links.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
