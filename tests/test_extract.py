import json
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from tests.helpers import tmp_cfg
from mindgap.extract import extract_day, redact, window

NY = ZoneInfo("America/New_York")


def row(dt, text, sid="s1", project="/p"):
    return json.dumps({"display": text, "timestamp": int(dt.timestamp() * 1000), "project": project, "sessionId": sid, "pastedContents": {}})


class Extract(unittest.TestCase):
    def setUp(self):
        self.cfg, self.root = tmp_cfg()

    def run_rows(self, rows, day=date(2026, 10, 26), cfg=None):
        f = self.root / "history.jsonl"
        f.write_text("\n".join(rows) + "\n")
        return extract_day(day, cfg or self.cfg, f)

    def test_day_boundaries_are_new_york_midnight(self):
        rows = [row(datetime(2026, 10, 25, 23, 59, 59, tzinfo=NY), "before"),
                row(datetime(2026, 10, 26, 0, 0, 0, tzinfo=NY), "first"),
                row(datetime(2026, 10, 26, 23, 59, 59, tzinfo=NY), "last"),
                row(datetime(2026, 10, 27, 0, 0, 0, tzinfo=NY), "after")]
        out = self.run_rows(rows)
        self.assertEqual([p["text"] for p in out["prompts"]], ["first", "last"])
        self.assertEqual(out["prompts"][0]["time"], "2026-10-26T00:00:00-04:00")
        self.assertEqual([p["id"] for p in out["prompts"]], ["2026-10-26-001", "2026-10-26-002"])

    def test_dst_change_day_is_25_hours(self):
        s, e = window(date(2026, 11, 1), NY)
        self.assertEqual(e.timestamp() - s.timestamp(), 25 * 3600)
        rows = [row(datetime(2026, 11, 1, 23, 30, tzinfo=NY), "late EST")]  # 04:30Z next day, still on 11-01 in NY
        self.assertEqual(len(self.run_rows(rows, date(2026, 11, 1))["prompts"]), 1)
        self.assertEqual(len(self.run_rows(rows, date(2026, 11, 2))["prompts"]), 0)

    def test_filters_and_counts(self):
        t = datetime(2026, 10, 26, 10, 0, tzinfo=NY)
        rows = [row(t, "/model fable"),
                row(t, "keep this"),
                row(t, "[Pasted text #1 +20 lines]"),
                row(t, "see [Pasted text #2 +3 lines] please"),
                row(t, "x" * 401)]
        out = self.run_rows(rows)
        self.assertEqual([p["text"] for p in out["prompts"]], ["keep this", "see  please"])
        self.assertEqual((out["slash"], out["empty_after_strip"], out["filtered_long"], out["with_paste_placeholder"]), (1, 1, 1, 2))

    def test_redaction(self):
        self.assertNotIn("sk-abcdefgh12345", redact("key sk-abcdefgh12345"))
        self.assertIn("[已脱敏]", redact("password: hunter2"))
        self.assertIn("[已脱敏]", redact("host 192.168.1.20"))

    def test_exclude_projects_and_bad_lines(self):
        cfg, _ = tmp_cfg(exclude_projects=["/secret"])
        t = datetime(2026, 10, 26, 10, 0, tzinfo=NY)
        out = self.run_rows([row(t, "a", project="/secret"), "not json", row(t, "b")], cfg=cfg)
        self.assertEqual([p["text"] for p in out["prompts"]], ["b"])


if __name__ == "__main__":
    unittest.main()
