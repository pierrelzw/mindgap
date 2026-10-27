import json
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.helpers import tmp_cfg
from mindgap import paths
from mindgap.pipeline import RunResult
from mindgap.tick import due_trigger, locked, pending_triggers, tick

NY = ZoneInfo("America/New_York")


def ny(*a):
    return datetime(*a, tzinfo=NY)


class Due(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(due_trigger(ny(2026, 10, 27, 17, 59), 18, 0), date(2026, 10, 26))
        self.assertEqual(due_trigger(ny(2026, 10, 27, 18, 0), 18, 0), date(2026, 10, 27))
        self.assertEqual(due_trigger(ny(2026, 10, 27, 18, 1), 18, 0), date(2026, 10, 27))

    def test_dst_change_day(self):
        # NY leaves DST on 2026-11-01: 18:00 EDT = 22:00Z on 10-31, 18:00 EST = 23:00Z on 11-01.
        utc = ZoneInfo("UTC")
        self.assertEqual(ny(2026, 10, 31, 18).astimezone(utc).hour, 22)
        self.assertEqual(ny(2026, 11, 1, 18).astimezone(utc).hour, 23)
        self.assertEqual(due_trigger(ny(2026, 11, 1, 17, 59), 18, 0), date(2026, 10, 31))
        self.assertEqual(due_trigger(ny(2026, 11, 1, 18, 0), 18, 0), date(2026, 11, 1))
        # Seen from Shanghai, 22:59Z on 11-01 is still before the 18:00 EST instant 23:00Z.
        now = datetime(2026, 11, 1, 22, 59, tzinfo=ZoneInfo("UTC")).astimezone(NY)
        self.assertEqual(due_trigger(now, 18, 0), date(2026, 10, 31))
        now = datetime(2026, 11, 1, 23, 0, tzinfo=ZoneInfo("UTC")).astimezone(NY)
        self.assertEqual(due_trigger(now, 18, 0), date(2026, 11, 1))

    def test_pending(self):
        self.assertEqual(pending_triggers(date(2026, 10, 26), date(2026, 10, 27), 7), [date(2026, 10, 27)])
        self.assertEqual(pending_triggers(date(2026, 10, 27), date(2026, 10, 27), 7), [])
        got = pending_triggers(date(2026, 10, 1), date(2026, 10, 27), 7)
        self.assertEqual(len(got), 7)
        self.assertEqual(got[0], date(2026, 10, 21))
        self.assertEqual(got[-1], date(2026, 10, 27))


class Tick(unittest.TestCase):
    def setUp(self):
        self.cfg, self.root = tmp_cfg()
        self.calls = []
        self.status = "ok"

    def fake(self, day, cfg, catchup=False, **kw):
        self.calls.append((day.isoformat(), catchup))
        return RunResult(day=day.isoformat(), status=self.status, stage="analyze" if self.status == "failed" else "", error="boom" if self.status == "failed" else "")

    def state(self):
        return json.loads(paths.state_file(self.cfg).read_text())

    def test_first_install_runs_only_latest_due_and_is_idempotent(self):
        now = ny(2026, 10, 27, 18, 5)
        tick(self.cfg, now=now, run_fn=self.fake)
        self.assertEqual(self.calls, [("2026-10-26", False)])
        tick(self.cfg, now=now + timedelta(minutes=1), run_fn=self.fake)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.state()["last_trigger_done"], "2026-10-27")

    def test_catch_up_in_order(self):
        paths.state_file(self.cfg).write_text(json.dumps({"last_trigger_done": "2026-10-23", "days": {}}))
        tick(self.cfg, now=ny(2026, 10, 27, 18, 5), run_fn=self.fake)
        self.assertEqual(self.calls, [("2026-10-23", True), ("2026-10-24", True), ("2026-10-25", True), ("2026-10-26", False)])

    def test_skips_days_already_done_manually(self):
        paths.state_file(self.cfg).write_text(json.dumps({"last_trigger_done": None, "days": {"2026-10-26": {"status": "ok", "attempts": 1}}}))
        tick(self.cfg, now=ny(2026, 10, 27, 18, 5), run_fn=self.fake)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state()["last_trigger_done"], "2026-10-27")

    def test_failure_stops_cools_down_then_retries_then_gives_up(self):
        self.status = "failed"
        t = ny(2026, 10, 27, 18, 0)
        tick(self.cfg, now=t, run_fn=self.fake)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.state()["last_trigger_done"])
        tick(self.cfg, now=t + timedelta(minutes=10), run_fn=self.fake)   # cooling down
        self.assertEqual(len(self.calls), 1)
        tick(self.cfg, now=t + timedelta(minutes=61), run_fn=self.fake)   # attempt 2
        tick(self.cfg, now=t + timedelta(minutes=122), run_fn=self.fake)  # attempt 3
        self.assertEqual(len(self.calls), 3)
        tick(self.cfg, now=t + timedelta(minutes=183), run_fn=self.fake)  # gives up and advances
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.state()["last_trigger_done"], "2026-10-27")

    def test_lock_contention_returns_zero_without_running(self):
        with locked(self.cfg) as got:
            self.assertTrue(got)
            self.assertEqual(tick(self.cfg, now=ny(2026, 10, 27, 18, 5), run_fn=self.fake), 0)
        self.assertEqual(self.calls, [])

    def test_dry_run_changes_nothing(self):
        tick(self.cfg, now=ny(2026, 10, 27, 18, 5), dry_run=True, run_fn=self.fake)
        self.assertEqual(self.calls, [])
        self.assertFalse(paths.state_file(self.cfg).exists())


if __name__ == "__main__":
    unittest.main()
