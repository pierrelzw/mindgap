import unittest
from zoneinfo import ZoneInfo

from tests import helpers  # noqa: F401
from mindgap.verify import norm, summary, verify_evidence

NY = ZoneInfo("America/New_York")
P = [{"id": "a", "time": "2026-10-26T08:06:27-04:00", "sessionId": "S1", "text": "安卓手机点击 一键导出会发生什么？"},
     {"id": "b", "time": "2026-10-26T09:00:00-04:00", "sessionId": "S2", "text": "另一个会话的话 要继续"}]


def ev(quote, sid="S1", time="2026-10-26T08:06:27-04:00"):
    return {"evidence": [{"quote": quote, "sessionId": sid, "time": time, "why_it_matters": "x"}]}


class Verify(unittest.TestCase):
    def one(self, *a, **k):
        return verify_evidence(ev(*a, **k), P, NY)[0]

    def test_exact_and_whitespace_differences(self):
        self.assertEqual(self.one("安卓手机点击一键导出会发生什么？")["status"], "verified")
        self.assertEqual(self.one("手机点击 一键导出")["prompt_index"], 0)

    def test_naive_time_is_read_in_the_report_timezone(self):
        self.assertEqual(self.one("一键导出", time="2026-10-26 08:06:27")["status"], "verified")

    def test_ellipsis_is_partial(self):
        r = self.one("安卓手机点击…会发生什么？")
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["prompt_index"], 0)

    def test_wrong_time_is_partial_and_flagged(self):
        r = self.one("一键导出", time="2026-10-26T12:00:00-04:00")
        self.assertEqual((r["status"], r["time_ok"]), ("partial", False))

    def test_quote_in_another_session_is_unverified(self):
        r = self.one("要继续", sid="S1")
        self.assertEqual(r["status"], "unverified")
        self.assertIn("另一个会话", r["note"])

    def test_unknown_session_and_made_up_quote(self):
        self.assertIn("属于另一个会话", self.one("一键导出", sid="nope")["note"])
        self.assertIn("会话 ID 不存在", self.one("完全编造的一句话", sid="nope")["note"])
        self.assertEqual(self.one("完全编造的一句话")["status"], "unverified")

    def test_summary_and_norm(self):
        v = verify_evidence({"evidence": ev("一键导出")["evidence"] + ev("编造")["evidence"]}, P, NY)
        self.assertEqual(summary(v), (1, 2))
        self.assertEqual(norm("a  b\n c"), "abc")


if __name__ == "__main__":
    unittest.main()
