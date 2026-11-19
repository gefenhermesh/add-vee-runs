"""Tests for campaign/tick.py. Run: python -m unittest campaign/test_tick.py"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tick  # noqa: E402

NOW = dt.datetime(2026, 11, 22, 9, 0, tzinfo=dt.timezone.utc)


def iso(minutes_ago):
    return (NOW - dt.timedelta(minutes=minutes_ago)).isoformat()


class TickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "campaign").mkdir()
        (root / "companies").mkdir()
        tick.ROOT, tick.STATE, tick.LOG = root, root / "campaign" / "state.json", root / "campaign" / "log.md"
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, prospects, cap=1):
        s = {"settings": {"max_concurrent_running": cap}, "prospects": prospects}
        tick.STATE.write_text(json.dumps(s))
        return tick.load_state()

    def status(self, slug, stage, minutes_ago=5, **kw):
        d = self.root / "companies" / slug
        d.mkdir(exist_ok=True)
        (d / "status.json").write_text(json.dumps({"stage": stage, "ts": iso(minutes_ago), **kw}))

    def kinds(self, actions):
        return [(a["do"], a["slug"], a.get("status") or a.get("kind")) for a in actions]

    def test_starts_first_queued_when_nothing_running(self):
        s = self.state([{"slug": "a", "company": "A", "status": "queued"}, {"slug": "b", "company": "B", "status": "queued"}])
        acts = tick.plan(s, {}, NOW)
        self.assertEqual(self.kinds(acts), [("start", "a", None)])
        self.assertIn("COMPANY_SESSION.md", acts[0]["prompt"])

    def test_nothing_to_do_while_one_is_working(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1"},
                        {"slug": "b", "company": "B", "status": "queued"}])
        self.status("a", "loop_b", minutes_ago=10)
        self.assertEqual(tick.plan(s, {"s1": {"status_bucket": "working"}}, NOW), [])

    def test_gate_notifies_once_and_frees_the_slot(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1"},
                        {"slug": "b", "company": "B", "status": "queued"}])
        self.status("a", "waiting_gate_1_2")
        acts = tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW)
        self.assertEqual(self.kinds(acts), [("mark", "a", "waiting_gate"), ("notify", "a", "gate"), ("start", "b", None)])
        tick.apply(s, [{**a, "ok": True, "session_id": "s2"} for a in acts], NOW)
        s = tick.load_state()
        self.assertEqual(tick.plan(s, {"s1": {"status_bucket": "idle"}, "s2": {"status_bucket": "working"}}, NOW), [])

    def test_after_gate_approval_company_counts_as_running_again(self):
        s = self.state([{"slug": "a", "company": "A", "status": "waiting_gate", "session_id": "s1", "notified": {"gate": "x"}},
                        {"slug": "b", "company": "B", "status": "queued"}])
        self.status("a", "loop_b")
        acts = tick.plan(s, {"s1": {"status_bucket": "working"}}, NOW)
        self.assertEqual(self.kinds(acts), [("mark", "a", "running")])

    def test_watchdog_nudges_then_marks_stuck(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1", "nudges": 0}])
        self.status("a", "loop_b", minutes_ago=200)
        acts = tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW)
        self.assertEqual(self.kinds(acts), [("nudge", "a", None)])
        s["prospects"][0]["nudges"] = 2
        acts = tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW)
        self.assertEqual(self.kinds(acts)[:2], [("mark", "a", "stuck"), ("notify", "a", "stuck")])

    def test_no_nudge_for_recent_progress(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1"}])
        self.status("a", "loop_b", minutes_ago=20)
        self.assertEqual(tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW), [])

    def test_done_notifies_with_draft(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1"}])
        self.status("a", "done", gmail_draft_id="r123")
        acts = tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW)
        self.assertEqual(self.kinds(acts), [("mark", "a", "done"), ("notify", "a", "done")])
        self.assertNotIn("missing", acts[1]["message"])

    def test_blocked_session_notifies_once(self):
        s = self.state([{"slug": "a", "company": "A", "status": "running", "session_id": "s1"}])
        self.status("a", "loop_c", minutes_ago=10)
        acts = tick.plan(s, {"s1": {"status_bucket": "blocked"}}, NOW)
        self.assertEqual(self.kinds(acts), [("notify", "a", "blocked")])
        s["prospects"][0]["notified"] = {"blocked": "x"}
        self.assertEqual(tick.plan(s, {"s1": {"status_bucket": "blocked"}}, NOW), [])

    def test_apply_records_and_logs(self):
        s = self.state([{"slug": "a", "company": "A", "status": "queued"}])
        acts = tick.plan(s, {}, NOW)
        tick.apply(s, [{**acts[0], "ok": True, "session_id": "s9"}], NOW)
        s = tick.load_state()
        self.assertEqual((s["prospects"][0]["status"], s["prospects"][0]["session_id"]), ("starting", "s9"))
        self.assertIn("start a", tick.LOG.read_text())

    def test_other_statuses_are_left_alone(self):
        s = self.state([{"slug": "bay", "company": "Bay", "status": "manual"}, {"slug": "x", "company": "X", "status": "done"}])
        self.assertEqual(tick.plan(s, {}, NOW), [])


if __name__ == "__main__":
    unittest.main()
