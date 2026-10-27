import copy
import json
import logging
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import tmp_cfg
from mindgap import analyze
from mindgap.analyze import analyze_day, build_prompt, parse_envelope
from mindgap.config import MindgapError
from mindgap.schema import validate

GOOD = {"blindspot": {"label_en": "X", "label_zh": "甲", "definition": "d"},
        "evidence": [{"time": "2026-10-26T08:06:27-04:00", "sessionId": "S1", "quote": "安卓手机点击", "why_it_matters": "w"},
                     {"time": "2026-10-26T09:00:00-04:00", "sessionId": "S2", "quote": "要继续", "why_it_matters": "w"}],
        "root_cause": "r", "book": {"title": "T", "author": "A", "year": 1989, "principle": "p", "why": "w"},
        "checklist": ["a", "b", "c"], "one_liner": "o", "confidence": "high"}
PROMPTS = {"date": "2026-10-26", "prompts": [
    {"id": "1", "time": "2026-10-26T08:06:27-04:00", "project": "/p", "sessionId": "S1", "text": "安卓手机点击一键导出"},
    {"id": "2", "time": "2026-10-26T09:00:00-04:00", "project": "/p", "sessionId": "S2", "text": "另一个会话要继续"}]}


def env(**kw):
    base = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.1, "num_turns": 1}
    base.update(kw)
    return json.dumps(base)


class Parse(unittest.TestCase):
    def test_structured_output_preferred(self):
        _, obj = parse_envelope(env(structured_output=GOOD, result="ignored"))
        self.assertEqual(obj["one_liner"], "o")

    def test_plain_and_fenced_result(self):
        self.assertEqual(parse_envelope(env(result=json.dumps(GOOD)))[1]["confidence"], "high")
        self.assertEqual(parse_envelope(env(result="```json\n" + json.dumps(GOOD) + "\n```"))[1]["confidence"], "high")

    def test_error_envelopes_raise(self):
        with self.assertRaises(MindgapError):
            parse_envelope(env(is_error=True, result="boom"))
        with self.assertRaises(MindgapError):
            parse_envelope(env(subtype="error_max_structured_output_retries"))
        with self.assertRaises(MindgapError):
            parse_envelope("not json")


class Schema(unittest.TestCase):
    def test_good_passes(self):
        self.assertEqual(validate(GOOD), [])

    def test_evidence_count_bounds(self):
        one = copy.deepcopy(GOOD); one["evidence"] = one["evidence"][:1]
        five = copy.deepcopy(GOOD); five["evidence"] = GOOD["evidence"] * 3
        self.assertTrue(validate(one))
        self.assertTrue(validate(five))

    def test_other_violations(self):
        bad = copy.deepcopy(GOOD); bad["confidence"] = "sure"; bad["extra"] = 1; bad["book"]["year"] = "1989"
        self.assertEqual(len(validate(bad)), 3)
        empty = copy.deepcopy(GOOD); empty["root_cause"] = " "
        self.assertTrue(validate(empty))


class Retry(unittest.TestCase):
    def setUp(self):
        self.cfg, self.root = tmp_cfg()
        self.work = self.root / "work"; self.work.mkdir()
        self.log = logging.getLogger("test-analyze")

    def run_with(self, outputs):
        it = iter(outputs)
        with mock.patch.object(analyze, "call_claude", side_effect=lambda *a, **k: (0, next(it), "", 1.0)):
            return analyze_day("2026-10-26", self.cfg, self.work, PROMPTS, self.log)

    def test_first_good_answer_is_accepted_without_retry(self):
        a, run = self.run_with([env(structured_output=GOOD)])
        self.assertEqual(run["attempts"], 1)
        self.assertTrue((self.work / "analysis.json").exists())

    def test_is_error_triggers_exactly_one_retry(self):
        a, run = self.run_with([env(is_error=True, result="x"), env(structured_output=GOOD)])
        self.assertEqual(run["attempts"], 2)

    def test_two_failures_raise(self):
        with self.assertRaises(MindgapError):
            self.run_with([env(is_error=True, result="x"), env(is_error=True, result="y")])

    def test_bad_quote_gets_feedback_and_best_attempt_wins(self):
        fake = copy.deepcopy(GOOD)
        fake["evidence"][0]["quote"] = "编造的话"
        fake["evidence"][1]["quote"] = "也是编造"
        prompts_seen = []
        outs = iter([env(structured_output=fake), env(structured_output=GOOD)])

        def call(prompt, *a, **k):
            prompts_seen.append(prompt)
            return 0, next(outs), "", 1.0
        with mock.patch.object(analyze, "call_claude", side_effect=call):
            a, run = analyze_day("2026-10-26", self.cfg, self.work, PROMPTS, self.log)
        self.assertEqual(run["attempts"], 2)
        self.assertIn("上一轮输出必须修正的问题", prompts_seen[1])
        self.assertEqual(a["evidence"][0]["quote"], "安卓手机点击")

    def test_prompt_contains_user_text_and_data(self):
        p = build_prompt(analyze.TEMPLATE_PATH.read_text(encoding="utf-8"), "2026-10-26", PROMPTS["prompts"])
        self.assertIn("You are an Epistemic Diagnostic Engine", p)
        self.assertIn("安卓手机点击一键导出", p)
        self.assertNotIn("{{", p)


if __name__ == "__main__":
    unittest.main()
