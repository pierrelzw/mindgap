import json, html, datetime, sys
from pathlib import Path
# usage: render.py [DAY ...]  — ingest spike/out/days/DAY into the archive, then re-render every day page + index
H = Path(__file__).parent; ARC = Path.home()/"Documents/my_mindgap"; e = html.escape
WD = "一二三四五六日"

def ingest(day):
    d = H/"out/days"/day; a = json.loads((d/"analysis.json").read_text()); p = json.loads((d/"prompts.json").read_text())
    stats = {k: p[k] for k in ("total_rows", "slash", "with_paste_placeholder", "filtered_long", "session_count")}
    stats.update(prompt_count=len(p["prompts"]), chars=sum(len(x["text"]) for x in p["prompts"]))
    rd = lambda n: json.loads((d/n).read_text()) if (d/n).exists() else None
    raw = rd("analyze-raw.json") or {}
    run = {"cost_usd": raw.get("total_cost_usd"), "turns": raw.get("num_turns"), "secs": round(raw.get("duration_ms", 0) / 1000), "dir": str(d)}
    out = ARC/day[:4]/day[5:7]/f"{day}.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"date": day, "stats": stats, "analysis": a, "links": rd("links.json"), "cites": rd("cites.json"), "run": run},
                              ensure_ascii=False, indent=2))

CSS = """:root{--fg:#222;--muted:#777;--bg:#fff;--card:#f6f6f6;--line:#ddd;--accent:#a60}
@media(prefers-color-scheme:dark){:root{--fg:#ddd;--muted:#999;--bg:#181818;--card:#262626;--line:#333;--accent:#e9a24a}}
body{font:16px/1.7 -apple-system,sans-serif;max-width:720px;margin:2em auto;padding:0 1em;color:var(--fg);background:var(--bg)}
a{color:var(--accent)}h2{border-bottom:1px solid var(--line);padding-bottom:.2em;margin-top:2em}
blockquote{margin:1em 0;padding:.5em 1em;border-left:4px solid var(--muted);background:var(--card)}
.q{border-color:var(--accent);font-family:Georgia,serif}footer,small,.muted{color:var(--muted)}footer{font-size:.85em;margin-top:3em}
nav{display:flex;justify-content:space-between;font-size:.9em;border-bottom:1px solid var(--line);padding-bottom:.5em}
nav .off{color:var(--muted)}
.tiles{display:flex;gap:1em;flex-wrap:wrap}.tile{flex:1;min-width:120px;background:var(--card);padding:.6em 1em;border-radius:6px}
.tile b{display:block;font-size:1.6em}
.bars{display:flex;align-items:flex-end;gap:4px;height:90px;border-bottom:1px solid var(--line)}
.bars a{flex:1;max-width:40px;background:var(--accent);opacity:.75;border-radius:3px 3px 0 0;text-decoration:none}
.bars a:hover{opacity:1}.bars .gap{flex:1;max-width:40px;height:2px;background:var(--line)}.barlab{display:flex;gap:4px;font-size:.7em;color:var(--muted)}.barlab span{flex:1;max-width:40px;text-align:center}
.day{display:block;background:var(--card);padding:.8em 1em;margin:1em 0;border-radius:6px;color:inherit;text-decoration:none}
.day:hover{outline:2px solid var(--accent)}
.ok{color:#2a8a3e}.bad{color:#c0392b}@media(prefers-color-scheme:dark){.ok{color:#5cc06f}.bad{color:#ff7b6b}}
blockquote a.src{text-decoration:none}.day h3{margin:.1em 0;font-size:1.05em}.day p{margin:.3em 0}"""

def page(title, body):
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"""

def rel(frm, to):  # relative link between two archive days
    return f"../../{to[:4]}/{to[5:7]}/{to}.html" if frm else f"{to[:4]}/{to[5:7]}/{to}.html"

def day_page(r, prev, nxt):
    a, s, day = r["analysis"], r["stats"], r["date"]; b = a["book"]
    L = r.get("links") or [{}] * len(a["evidence"])
    def chk(l):
        if not l: return "<span class=muted>未核对</span>"
        return (f"<span class={'ok' if l['in_input'] else 'bad'}>{'✓' if l['in_input'] else '✗'} 在分析输入中</span> · "
                + (f"<span class=bad>⚠ 会话里只找到 {l['delta_s']:.0f} 秒外的同文消息，可能不是这一条</span>" if l['in_session'] and not l.get('time_ok', True) else
                 f"<span class={'ok' if l['in_session'] else 'bad'}>{'✓' if l['in_session'] else '✗'} 在会话原文中" + (f"（时间差 {l['delta_s']} 秒）" if l.get("delta_s") is not None else "") + "</span>")
                + (" · <span class=muted>这条是在 AI 回复中途插入的，对话页里不单独显示，链接跳到它被接收后的下一条消息</span>" if l.get("queued") else ""))
    ev = "".join(f"<blockquote>{e(x['quote'])}<br><small>claude-code · {e(x['session'][:8])}… · {e(x['time'])}"
                 + (f" · <a href='../../{e(l['href'])}'>查看原对话 ↗</a>" if l.get("href") else "") + f"<br>{chk(l)}</small></blockquote>"
                 for x, l in zip(a["evidence"], L))
    C = {c["i"]: c for c in (r.get("cites") or [])}
    ST = {"verified": ("ok", "✓ 网页上逐字找到"), "partial": ("bad", "⚠ 部分段落在网页上未找到"), "not_on_page": ("bad", "✗ 网页上未找到"),
          "fetch_failed": ("bad", "✗ 网页抓取失败"), "no_url": ("bad", "✗ 没找到公开出处"),
          "paraphrase_ok": ("muted", "转述，无法逐字核对；对应的原句在网页上找到，链接会高亮该句"), "paraphrase_unanchored": ("bad", "⚠ 转述，对应的原句在网页上未找到")}
    PRIMARY = ("archive.org", "gutenberg.org", "nlp.stanford.edu", "books.google.")  # full text / author's own site
    def tier(u):
        if not u: return ""
        return " <b class=ok>[一手：全文/官方]</b>" if any(d in u for d in PRIMARY) else " <b class=muted>[二手转引：只说明别人也这么引过，不等于原书原文]</b>"
    def src(c):
        if not c: return "<br><span class=muted>出处未核对</span>"
        k, t = ST[c["status"]]; t += tier(c.get("url"))
        miss = "".join(f"<br>未找到：“{e(m)}”" for m in c.get("missing") or [])
        return (f"<br><span class={k}>{t}</span>" + (f" · <a class=src href='{e(c['href'])}'>打开出处并高亮 ↗</a>" if c.get("href") else "")
                + f"<span class=muted>{miss}</span>")
    ex = "".join(f"<blockquote class='q'>{e(x['text'])}{' <b>(转述)</b>' if x['is_paraphrase'] else ''}<br><small>{e(x['location'])} · {e(x['edition'])}{src(C.get(i))}</small></blockquote><p>{e(x['commentary'])}</p>" for i, x in enumerate(a["excerpts"]))
    ac = "".join(f"<li>{e(x)}</li>" for x in a["actions"])
    nav = (f"<nav>{f'<a href={rel(1, prev)!r}>← {prev}</a>' if prev else '<span class=off>← 无</span>'}"
           f"<a href='../../index.html'>总览</a>"
           f"{f'<a href={rel(1, nxt)!r}>{nxt} →</a>' if nxt else '<span class=off>无 →</span>'}</nav>")
    wd = WD[datetime.date.fromisoformat(day).weekday()]
    return page(f"mindgap {day}", f"""{nav}<h1>{day}（周{wd}）复盘</h1>
<h2>1. 一句话结论</h2><p><b>{e(a['blindspot']['label'])}</b></p><p>{e(a['blindspot']['summary'])}</p>
<h2>2. 证据</h2>{ev}
<h2>3. 为什么这是盲点</h2><p>{e(a['why'])}</p>
<h2>4. 推荐书籍</h2><p>《{e(b['title'])}》— {e(b['author'])}（{b['year']}）</p><p>{e(b['reason'])}</p>
<h2>5. 书中片段</h2>{ex}
<h2>6. 明天就能用的做法</h2><ol>{ac}</ol>
<h2>核验</h2><ul>
<li>证据：{sum(1 for l in L if l and l['in_input'] and l['in_session'] and l.get('time_ok', True))}/{len(a['evidence'])} 条在分析输入和会话原文中都找到（脚本逐字比对，不依赖模型）。点“查看原对话”可跳到那一句，对话由 claude-code-transcripts 生成。</li>
<li>引文：{sum(1 for c in C.values() if c['status'] == 'verified')}/{len(a['excerpts'])} 段在公开网页上逐字找到，{sum(1 for c in C.values() if c['status'] == 'paraphrase_ok')} 段是转述，已在网页上找到对应原句。网址由另一个独立的 claude -p 查找，再由脚本抓取网页比对文字（OCR 允许一处错字）；“打开出处并高亮”会让浏览器直接滚动到原文。</li>
<li>原始数据：<a href='file://{e(r.get('run', {}).get('dir', ''))}/'>{e(r.get('run', {}).get('dir', ''))}</a>（prompts.json 是模型输入，analyze-raw.json 是模型原样输出，links.json / cites.json 是核验结果）。本次分析耗时 {r.get('run', {}).get('secs')} 秒，{r.get('run', {}).get('turns')} 轮，${r.get('run', {}).get('cost_usd') or 0:.2f}。</li></ul>{nav}
<footer>数据来源：Claude Code history.jsonl，{s['total_rows']} 行，{s['session_count']} 个会话；有效 prompt {s['prompt_count']} 条；斜杠命令 {s['slash']} 条；超长过滤 {s['filtered_long']} 条。生成时间 {datetime.datetime.now().isoformat(timespec='seconds')}（spike）</footer>""")

def index_page(rs):
    n = sum(r["stats"]["prompt_count"] for r in rs); mx = max(r["stats"]["prompt_count"] for r in rs) or 1
    d0 = datetime.date.fromisoformat(rs[0]["date"]); by = {r["date"]: r for r in rs}  # every calendar day in range, so gaps show
    days = [(d0 + datetime.timedelta(k)).isoformat() for k in range((datetime.date.fromisoformat(rs[-1]["date"]) - d0).days + 1)]
    bars = "".join(f"<a href={rel(0, d)!r} title='{d}：{by[d]['stats']['prompt_count']} 条' style='height:{max(by[d]['stats']['prompt_count'] / mx * 100, 2):.0f}%'></a>"
                   if d in by else f"<span class=gap title='{d}：无记录'></span>" for d in days)
    labs = "".join(f"<span>{d[5:]}</span>" for d in days)
    cards = "".join(f"""<a class=day href={rel(0, r['date'])!r}><small>{r['date']} 周{WD[datetime.date.fromisoformat(r['date']).weekday()]} · {r['stats']['prompt_count']} 条 prompt · {r['stats']['session_count']} 个会话</small>
<h3>{e(r['analysis']['blindspot']['label'])}</h3><p>{e(r['analysis']['blindspot']['summary'])}</p>
<p class=muted>📖 《{e(r['analysis']['book']['title'])}》— {e(r['analysis']['book']['author'])}</p>
<small>核验：证据 {sum(1 for l in (r.get('links') or []) if l['in_input'] and l['in_session'] and l.get('time_ok', True))}/{len(r['analysis']['evidence'])} · 引文 {sum(1 for c in (r.get('cites') or []) if c['status'] == 'verified')}/{len(r['analysis']['excerpts'])}</small></a>""" if r else f"<p class=muted>{d} 周{WD[datetime.date.fromisoformat(d).weekday()]} · 无记录</p>" for d, r in ((d, by.get(d)) for d in reversed(days)))
    books = "".join(f"<li>《{e(r['analysis']['book']['title'])}》— {e(r['analysis']['book']['author'])}（{r['analysis']['book']['year']}）<small> · <a href={rel(0, r['date'])!r}>{r['date']}</a></small></li>" for r in rs)
    return page("mindgap 总览", f"""<h1>mindgap 总览</h1>
<div class=tiles><div class=tile><b>{len(rs)}/{len(days)}</b>天有复盘</div><div class=tile><b>{n}</b>条 prompt</div><div class=tile><b>{rs[0]['date'][5:]} – {rs[-1]['date'][5:]}</b>覆盖范围</div></div>
<h2>每日 prompt 量</h2><div class=bars>{bars}</div><div class=barlab>{labs}</div>
<h2>每日盲点</h2>{cards}
<h2>书单</h2><ol>{books}</ol>
<footer>由存档目录下的 YYYY/MM/*.json 生成，共 {len(rs)} 份。生成时间 {datetime.datetime.now().isoformat(timespec='seconds')}（spike）</footer>""")

for day in sys.argv[1:]: ingest(day)
rs = sorted((json.loads(f.read_text()) for f in ARC.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*.json")), key=lambda r: r["date"])
for i, r in enumerate(rs):
    p = ARC/r["date"][:4]/r["date"][5:7]/f"{r['date']}.html"
    p.write_text(day_page(r, rs[i-1]["date"] if i else None, rs[i+1]["date"] if i+1 < len(rs) else None)); print(p)
(ARC/"index.html").write_text(index_page(rs)); print(ARC/"index.html")
