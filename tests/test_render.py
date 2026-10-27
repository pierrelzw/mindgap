import copy
import json
import re
import unittest
from urllib.parse import unquote

from tests.helpers import tmp_cfg
from mindgap import paths
from mindgap.render import day_page, index_page, load_archive, render_all

ANALYSIS = {"blindspot": {"label_en": "X", "label_zh": "甲<script>", "definition": "d"},
            "evidence": [{"time": "2026-10-26T08:06:27-04:00", "sessionId": "S1abcdefgh", "quote": "引文 <b>", "why_it_matters": "w"}],
            "root_cause": "r", "book": {"title": "T", "author": "A", "year": 1989, "principle": "p", "why": "w"},
            "checklist": ["a", "b", "c"], "one_liner": "o", "confidence": "low"}


def rec(day, status="ok", href="transcripts/S1abcdefgh/index.html"):
    return {"schema_version": 2, "date": day, "status": status, "generated_at": "2026-10-27T00:00:00+08:00",
            "stats": {"total_rows": 5, "slash": 0, "with_paste_placeholder": 0, "empty_after_strip": 0, "filtered_long": 0,
                      "session_count": 1, "prompt_count": 9 if status == "ok" else 2, "chars": 10},
            "analysis": copy.deepcopy(ANALYSIS) if status == "ok" else None,
            "verify": [{"i": 0, "status": "verified", "prompt_index": 0, "session_ok": True, "time_ok": True, "delta_s": 0, "note": ""}] if status == "ok" else None,
            "links": [{"i": 0, "href": href, "delta_s": 0.5, "queued": False, "in_session": True}] if status == "ok" else None,
            "run": {"cost_usd": 0.1, "turns": 1, "secs": 10, "model": "m", "attempts": 1, "work_dir": "/tmp/w"}}


class Render(unittest.TestCase):
    def setUp(self):
        self.cfg, self.root = tmp_cfg()

    def write(self, r):
        p = paths.day_json(self.cfg, r["date"]); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False))

    def test_empty_archive_does_not_crash(self):
        idx = render_all(self.cfg)
        self.assertIn("暂无报告", idx.read_text())

    def test_v1_json_is_ignored(self):
        v1 = {"date": "2026-10-15", "analysis": {"blindspot": {"label": "旧"}}}
        p = paths.day_json(self.cfg, "2026-10-15"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v1))
        self.assertEqual(load_archive(self.cfg), [])

    def test_html_is_escaped(self):
        h = day_page(rec("2026-10-26"), None, None)
        self.assertNotIn("甲<script>", h)
        self.assertIn("甲&lt;script&gt;", h)
        self.assertIn("引文 &lt;b&gt;", h)

    def test_insufficient_day_and_gaps_and_links(self):
        self.write(rec("2026-10-24", "insufficient"))
        self.write(rec("2026-10-26"))
        self.write(rec("2026-10-27"))
        (self.root / "transcripts" / "S1abcdefgh").mkdir(parents=True)
        (self.root / "transcripts" / "S1abcdefgh" / "index.html").write_text("x")
        idx = render_all(self.cfg)
        text = idx.read_text()
        self.assertIn("数据不足", text)
        self.assertIn("2026-10-25 周日 · 无记录", text)  # calendar gap is visible
        self.assertIn("2026-10-24", (self.root / "2026/10/2026-10-24.html").read_text())
        # every relative link in every generated page resolves to a file
        for page in [idx, *self.root.glob("2026/10/*.html")]:
            for h in re.findall(r"href='([^']+)'", page.read_text()):
                if h.startswith(("http", "file:")):
                    continue
                self.assertTrue((page.parent / unquote(h.split("#")[0])).resolve().exists(), (page.name, h))


if __name__ == "__main__":
    unittest.main()
