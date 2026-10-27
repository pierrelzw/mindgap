import json, re, sys, subprocess, time, html, urllib.request, urllib.parse
from pathlib import Path
# usage: cite.py DAY — ask a separate `claude -p` for a public URL per excerpt, then fetch each URL ourselves and check the text is there
H = Path(__file__).parent; D = H/"out/days"/sys.argv[1]
a = json.loads((D/"analysis.json").read_text()); b = a["book"]
items = [{"i": i, "text": x["text"], "location": x["location"], "edition": x["edition"], "is_paraphrase": x["is_paraphrase"]} for i, x in enumerate(a["excerpts"])]
PROMPT = f"""下面是声称出自《{b['title']}》（{b['author']}, {b['year']}）的若干片段。请用 WebSearch/WebFetch 为每个片段找一个**公开可访问、页面正文里能直接看到这段文字**的网址（优先：作者/出版社官网的免费全文、Project Gutenberg、archive.org 的全文 txt、Google Books 可预览页、可信的引用页）。
- 必须亲自 WebFetch 确认页面里有这段文字（至少一个完整句子）再填；找不到就填 null，不要猜。
- 转述（is_paraphrase=true）的片段，找对应原文所在页面即可。
只输出一个 JSON 数组，不要代码块：[{{"i":0,"url":"...或null","found_sentence":"页面上实际出现的一句原文","note":"简短说明"}}]

{json.dumps(items, ensure_ascii=False, indent=1)}"""
if (D/"cite-found.json").exists(): found = json.loads((D/"cite-found.json").read_text())  # re-verify without paying again
else:
    cmd = ["/Users/ai/.local/share/mise/installs/node/lts/bin/claude", "-p", "--output-format", "json", "--allowedTools", "WebSearch,WebFetch",
           "--no-session-persistence", "--permission-mode", "dontAsk", "--max-budget-usd", "2"]
    t = time.time(); r = subprocess.run(cmd, input=PROMPT, capture_output=True, text=True, timeout=900)
    (D/"cite-raw.json").write_text(r.stdout); env = json.loads(r.stdout); res = env["result"]
    print("rc", r.returncode, "secs", round(time.time() - t, 1), "cost", env.get("total_cost_usd"), "turns", env.get("num_turns"))
    try: found = json.loads(res)
    except Exception: found = json.loads(re.search(r"(\[.*\])", res, re.S).group(1))
    (D/"cite-found.json").write_text(json.dumps(found, ensure_ascii=False, indent=2))

words = lambda s: re.findall(r"[A-Za-z0-9']+", s.lower())
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) mindgap-spike"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", raw)))

letters = lambda s: re.sub(r"[^a-z]", "", s.lower())  # drops punctuation, spacing and OCR word breaks ("writ ten")
segs = lambda s: [g.strip(" .") for g in re.split(r"…|\.\.\.", s) if len(g.split()) >= 3]  # "…" joins separate passages
def found_in(g, page):  # tolerate one local OCR error ("d wise man"): at most one 12-letter shingle may be missing
    if len(g) < 20: return False  # e.g. Chinese paraphrase: no Latin text to compare, never a match
    if g in page: return True
    sh = [g[k:k + 12] for k in range(0, max(1, len(g) - 11), 4)]
    return len(sh) >= 4 and sum(x not in page for x in sh) <= 1
out = []
for f in found:
    x = a["excerpts"][f["i"]]; rec = {"i": f["i"], "url": f.get("url"), "note": f.get("note"), "status": "no_url", "match": 0.0}
    if rec["url"]:
        para = x["is_paraphrase"]  # a paraphrase can't match verbatim: check the original sentence the finder quoted instead
        ss = [f.get("found_sentence") or ""] if para else segs(x["text"]) or [x["text"]]
        try:
            page = letters(fetch(rec["url"])); hit = [found_in(letters(g), page) for g in ss]
            rec["match"] = round(sum(hit) / len(hit), 2); rec["missing"] = [g for g, h in zip(ss, hit) if not h]
            rec["status"] = ("paraphrase_ok" if all(hit) else "paraphrase_unanchored") if para else "verified" if all(hit) else "partial" if any(hit) else "not_on_page"
        except Exception as ex:
            rec["status"] = "fetch_failed"; rec["error"] = str(ex)[:200]
        q = lambda s: urllib.parse.quote(s, safe="").replace("-", "%2D")  # text fragment per passage, so the browser highlights each
        frag = "&".join("text=" + (q(" ".join(g.split()[:5])) + "," + q(" ".join(g.split()[-5:])) if len(g.split()) > 10 else q(g)) for g in ss)
        rec["href"] = rec["url"] + (":~:" if "#" in rec["url"] else "#:~:") + frag
    out.append(rec); print(rec["i"], rec["status"], rec["match"], rec.get("missing"), rec["url"])
(D/"cites.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
