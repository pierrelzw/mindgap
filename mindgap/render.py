"""Render the self-contained HTML archive (inline CSS, no JS, relative links, light/dark)."""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import paths
from .config import Config
from .verify import summary

SCHEMA_VERSION = 2
e = html.escape
WD = "一二三四五六日"

CSS = """:root{--fg:#222;--muted:#777;--bg:#fff;--card:#f6f6f6;--line:#ddd;--accent:#a60;--ok:#2a8a3e;--bad:#c0392b;--warn:#b7791f}
@media(prefers-color-scheme:dark){:root{--fg:#ddd;--muted:#999;--bg:#181818;--card:#262626;--line:#333;--accent:#e9a24a;--ok:#5cc06f;--bad:#ff7b6b;--warn:#e9c46a}}
body{font:16px/1.7 -apple-system,sans-serif;max-width:720px;margin:2em auto;padding:0 1em;color:var(--fg);background:var(--bg)}
a{color:var(--accent)}h2{border-bottom:1px solid var(--line);padding-bottom:.2em;margin-top:2em}
blockquote{margin:1em 0;padding:.5em 1em;border-left:4px solid var(--muted);background:var(--card)}
blockquote.v{border-color:var(--ok)}blockquote.p{border-color:var(--warn)}blockquote.u{border-color:var(--bad)}
footer,small,.muted{color:var(--muted)}footer{font-size:.85em;margin-top:3em}
nav{display:flex;justify-content:space-between;font-size:.9em;border-bottom:1px solid var(--line);padding-bottom:.5em}
nav .off{color:var(--muted)}
.tiles{display:flex;gap:1em;flex-wrap:wrap}.tile{flex:1;min-width:120px;background:var(--card);padding:.6em 1em;border-radius:6px}
.tile b{display:block;font-size:1.6em}
.bars{display:flex;align-items:flex-end;gap:4px;height:90px;border-bottom:1px solid var(--line)}
.bars a{flex:1;max-width:40px;background:var(--accent);opacity:.75;border-radius:3px 3px 0 0;text-decoration:none}
.bars a.ins{background:var(--muted);opacity:.35}.bars a:hover{opacity:1}
.bars .gap{flex:1;max-width:40px;height:2px;background:var(--line)}
.barlab{display:flex;gap:4px;font-size:.7em;color:var(--muted)}.barlab span{flex:1;max-width:40px;text-align:center}
.day{display:block;background:var(--card);padding:.8em 1em;margin:1em 0;border-radius:6px;color:inherit;text-decoration:none}
.day:hover{outline:2px solid var(--accent)}.day h3{margin:.1em 0;font-size:1.05em}.day p{margin:.3em 0}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.badge{display:inline-block;font-size:.75em;padding:0 .6em;border-radius:1em;background:var(--card);border:1px solid var(--line);color:var(--muted)}
.en{color:var(--muted);font-size:.9em}ul.check{list-style:none;padding-left:0}ul.check li{margin:.4em 0}"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>')


def rel(from_day_page: bool, to: str) -> str:
    return f"../../{to[:4]}/{to[5:7]}/{to}.html" if from_day_page else f"{to[:4]}/{to[5:7]}/{to}.html"


def _wd(day: str) -> str:
    return WD[date.fromisoformat(day).weekday()]


# ---------------------------------------------------------------- archive

def _stats(prompts: dict) -> dict:
    ps = prompts["prompts"]
    s = {k: prompts.get(k, 0) for k in ("total_rows", "slash", "with_paste_placeholder", "empty_after_strip", "filtered_long", "session_count")}
    s.update(prompt_count=len(ps), chars=sum(len(p["text"]) for p in ps))
    return s


def ingest(day: str, work: Path, cfg: Config, status: str, analysis: dict | None, verify: list | None,
           links: list | None, run: dict) -> Path:
    prompts = json.loads((work / "prompts.json").read_text(encoding="utf-8"))
    rec = {"schema_version": SCHEMA_VERSION, "date": day, "status": status,
           "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "stats": _stats(prompts), "analysis": analysis, "verify": verify, "links": links,
           "run": {**run, "work_dir": str(work)}}
    out = paths.day_json(cfg, day)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


def load_archive(cfg: Config) -> list[dict]:
    rs = []
    for f in cfg.archive.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("schema_version") == SCHEMA_VERSION and r.get("date"):
            rs.append(r)
    return sorted(rs, key=lambda r: r["date"])


# ---------------------------------------------------------------- pages

_EV = {"verified": ("v", "ok", "✓ 逐字命中"), "partial": ("p", "warn", "⚠ 部分命中"), "unverified": ("u", "bad", "✗ 未命中")}


def _nav(prev, nxt):
    p = f"<a href='{rel(True, prev)}'>← {prev}</a>" if prev else "<span class=off>← 无</span>"
    n = f"<a href='{rel(True, nxt)}'>{nxt} →</a>" if nxt else "<span class=off>无 →</span>"
    return f"<nav>{p}<a href='../../index.html'>总览</a>{n}</nav>"


def _footer(r: dict) -> str:
    s = r["stats"]
    return (f"<footer>数据来源：Claude Code history.jsonl，{s['total_rows']} 行，{s['session_count']} 个会话；"
            f"有效 prompt {s['prompt_count']} 条；斜杠命令 {s['slash']} 条；超长过滤 {s['filtered_long']} 条。"
            f"生成时间 {e(r.get('generated_at', ''))}</footer>")


def insufficient_page(r: dict, prev, nxt, min_prompts: int | None = None) -> str:
    day, s = r["date"], r["stats"]
    thr = f"，低于阈值 {min_prompts}" if min_prompts else ""
    return page(f"mindgap {day}", f"""{_nav(prev, nxt)}<h1>{day}（周{_wd(day)}）复盘</h1>
<p>当天有效 prompt {s['prompt_count']} 条{thr}，未生成诊断。数据太少时硬做诊断只会得到泛泛而谈的结论。</p>{_footer(r)}""")


def day_page(r: dict, prev, nxt) -> str:
    a, day, run = r["analysis"], r["date"], r.get("run") or {}
    ver = r.get("verify") or []
    links = r.get("links") or []
    bs, bk = a["blindspot"], a["book"]
    ev_html = []
    for i, ev in enumerate(a["evidence"]):
        v = ver[i] if i < len(ver) else None
        l = links[i] if i < len(links) else {}
        cls, color, label = _EV.get(v["status"] if v else "unverified", _EV["unverified"])
        extra = ""
        if v and v["status"] != "verified" and v.get("note"):
            extra = f" · <span class={color}>{e(v['note'])}</span>"
        if l.get("delta_s") is not None and l["delta_s"] > 60:
            extra += f" · <span class=warn>会话里最接近的同文消息在 {l['delta_s']:.0f} 秒之外</span>"
        if l.get("queued"):
            extra += " · <span class=muted>这条是在 AI 回复中途插入的，对话页不单独显示，链接跳到它之后的下一条消息</span>"
        link = f" · <a href='../../{e(l['href'])}'>查看原对话 ↗</a>" if l.get("href") else ""
        ev_html.append(f"<blockquote class={cls}>{e(ev['quote'])}<br><small>{e(ev['sessionId'][:8])}… · {e(ev['time'])}{link}"
                       f"<br><span class={color}>{label}</span>{extra}</small></blockquote>"
                       f"<p class=muted>{e(ev['why_it_matters'])}</p>")
    n_ok, n_all = summary(ver) if ver else (0, len(a["evidence"]))
    checks = "".join(f"<li>☐ {e(x)}</li>" for x in a["checklist"])
    wd = e(str(run.get("work_dir", "")))
    cost = run.get("cost_usd") or 0
    return page(f"mindgap {day}", f"""{_nav(prev, nxt)}<h1>{day}（周{_wd(day)}）复盘</h1>
<p><b>{e(a['one_liner'])}</b> <span class=badge>置信度 {e(a['confidence'])}</span>{" <span class=badge>补跑</span>" if run.get('catchup') else ""}</p>
<h2>1. 盲点标签与定义</h2><p><b>{e(bs['label_zh'])}</b><br><span class=en>{e(bs['label_en'])}</span></p><p>{e(bs['definition'])}</p>
<h2>2. 可核验的原话证据</h2>{''.join(ev_html)}
<h2>3. 根因分析</h2><p>{e(a['root_cause'])}</p>
<h2>4. 经典书籍与理论原理</h2><p>《{e(bk['title'])}》— {e(bk['author'])}（{bk['year']}）</p><p><b>原理：</b>{e(bk['principle'])}</p><p>{e(bk['why'])}</p>
<h2>5. 明日微清单</h2><ul class=check>{checks}</ul>
<h2>核验</h2><ul>
<li>证据：{n_ok}/{n_all} 条在原始 prompt 中逐字找到，且会话和时间都对得上。比对由脚本完成，不依赖模型。</li>
<li>⚠ 表示引文含省略号或时间对不上，✗ 表示在该会话的 prompt 里找不到这句话。失败的条目标红保留，不会删除。</li>
<li>“查看原对话”跳到 claude-code-transcripts 生成的对话页中对应的消息。</li>
<li>原始数据：<a href='file://{wd}/'>{wd}</a>（prompts.json 是模型输入，analyze-raw.json 是模型原样输出，verify.json 是核验结果）。本次分析 {run.get('secs')} 秒，{run.get('turns')} 轮，${cost:.2f}，模型 {e(str(run.get('model')))}，尝试 {run.get('attempts')} 次。</li></ul>
{_nav(prev, nxt)}{_footer(r)}""")


def _next_trigger(cfg: Config, now: datetime | None = None) -> datetime:
    now = now or datetime.now(cfg.tz)
    d = now.date()
    t = datetime(d.year, d.month, d.day, cfg.hour, cfg.minute, tzinfo=cfg.tz)
    if now.timestamp() >= t.timestamp():
        d += timedelta(days=1)
        t = datetime(d.year, d.month, d.day, cfg.hour, cfg.minute, tzinfo=cfg.tz)
    return t


def _last_run(cfg: Config) -> dict | None:
    f = paths.runs_file(cfg)
    if not f.exists():
        return None
    lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    try:
        return json.loads(lines[-1]) if lines else None
    except ValueError:
        return None


def index_page(rs: list[dict], cfg: Config | None = None) -> str:
    foot_run = ""
    if cfg is not None:
        nt = _next_trigger(cfg)
        lr = _last_run(cfg)
        bits = [f"下次触发 {nt.strftime('%Y-%m-%d %H:%M %Z')}（本机 {nt.astimezone().strftime('%m-%d %H:%M')}）"]
        if lr:
            bits.insert(0, f"最近运行 {e(str(lr.get('date')))} · {e(str(lr.get('status')))} · {lr.get('duration_s')} 秒 · ${(lr.get('cost_usd') or 0):.2f}"
                        + (f" · 失败于 {e(str(lr.get('stage')))}" if lr.get("status") == "failed" else ""))
        foot_run = "<p class=muted>" + "<br>".join(bits) + "</p>"
    if not rs:
        return page("mindgap 总览", f"<h1>mindgap 总览</h1><p>暂无报告。</p>{foot_run}")
    ok = [r for r in rs if r["status"] == "ok"]
    n = sum(r["stats"]["prompt_count"] for r in rs)
    mx = max(r["stats"]["prompt_count"] for r in rs) or 1
    d0, d1 = date.fromisoformat(rs[0]["date"]), date.fromisoformat(rs[-1]["date"])
    by = {r["date"]: r for r in rs}
    days = [(d0 + timedelta(k)).isoformat() for k in range((d1 - d0).days + 1)]
    bars = "".join(
        (f"<a class={'ins' if by[d]['status'] != 'ok' else 'ok'} href='{rel(False, d)}' title='{d}：{by[d]['stats']['prompt_count']} 条"
         f"{'（数据不足）' if by[d]['status'] != 'ok' else ''}' style='height:{max(by[d]['stats']['prompt_count'] / mx * 100, 2):.0f}%'></a>")
        if d in by else f"<span class=gap title='{d}：无记录'></span>" for d in days)
    labs = "".join(f"<span>{d[5:]}</span>" for d in days)
    cards = []
    for d in reversed(days):
        r = by.get(d)
        if not r:
            cards.append(f"<p class=muted>{d} 周{_wd(d)} · 无记录</p>")
        elif r["status"] != "ok":
            cards.append(f"<a class=day href='{rel(False, d)}'><small>{d} 周{_wd(d)} · {r['stats']['prompt_count']} 条 prompt</small>"
                         f"<h3 class=muted>数据不足</h3></a>")
        else:
            a = r["analysis"]
            n_ok, n_all = summary(r.get("verify") or [])
            cards.append(f"<a class=day href='{rel(False, d)}'><small>{d} 周{_wd(d)} · {r['stats']['prompt_count']} 条 prompt · {r['stats']['session_count']} 个会话</small>"
                         f"<h3>{e(a['blindspot']['label_zh'])}</h3><p>{e(a['one_liner'])}</p>"
                         f"<p class=muted>📖 《{e(a['book']['title'])}》— {e(a['book']['author'])}</p>"
                         f"<small>核验：证据 {n_ok}/{n_all or len(a['evidence'])}</small></a>")
    books = "".join(f"<li>《{e(r['analysis']['book']['title'])}》— {e(r['analysis']['book']['author'])}（{r['analysis']['book']['year']}）"
                    f"<small> · <a href='{rel(False, r['date'])}'>{r['date']}</a></small></li>" for r in ok)
    return page("mindgap 总览", f"""<h1>mindgap 总览</h1>
<div class=tiles><div class=tile><b>{len(ok)}/{len(days)}</b>天有复盘</div><div class=tile><b>{n}</b>条 prompt</div><div class=tile><b>{rs[0]['date'][5:]} – {rs[-1]['date'][5:]}</b>覆盖范围</div></div>
<h2>每日 prompt 量</h2><div class=bars>{bars}</div><div class=barlab>{labs}</div>
<h2>每日盲点</h2>{''.join(cards)}
<h2>书单</h2><ol>{books}</ol>{foot_run}
<footer>由存档目录下的 YYYY/MM/*.json 生成，共 {len(rs)} 份。生成时间 {datetime.now().astimezone().isoformat(timespec='seconds')}</footer>""")


def render_all(cfg: Config) -> Path:
    rs = load_archive(cfg)
    for i, r in enumerate(rs):
        prev = rs[i - 1]["date"] if i else None
        nxt = rs[i + 1]["date"] if i + 1 < len(rs) else None
        p = paths.day_html(cfg, r["date"])
        p.parent.mkdir(parents=True, exist_ok=True)
        body = day_page(r, prev, nxt) if r["status"] == "ok" and r.get("analysis") else insufficient_page(r, prev, nxt, cfg.min_prompts)
        p.write_text(body, encoding="utf-8")
    idx = cfg.archive / "index.html"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(index_page(rs, cfg), encoding="utf-8")
    return idx
