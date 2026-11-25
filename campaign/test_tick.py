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
        self.assertIn("docs/campaign/company-session.md", acts[0]["prompt"])

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
        self.assertEqual(self.kinds(acts), [("mark", "a", "done"), ("draft", "a", None), ("notify", "a", "done")])
        s["prospects"][0]["gmail_draft_id"] = "r1"
        self.assertEqual(self.kinds(tick.plan(s, {"s1": {"status_bucket": "idle"}}, NOW)),
                         [("mark", "a", "done"), ("notify", "a", "done")])

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


class PriorityTest(unittest.TestCase):
    def test_seo_job_started_first_with_track_prompt(self):
        st = {"settings": {"max_concurrent_running": 1}, "prospects": [
            {"slug": "a", "company": "A", "domain": "a.io", "status": "queued"},
            {"slug": "b", "company": "B", "domain": "b.io", "status": "queued", "priority": 1, "track": "seo_job",
             "job": {"title": "SEO Lead", "url": "https://x/1", "posted": "2026-11-21"}}]}
        acts = [a for a in tick.plan(st, {}, NOW) if a["do"] == "start"]
        self.assertEqual([a["slug"] for a in acts], ["b"])
        self.assertIn("Track seo_job", acts[0]["prompt"])
        self.assertIn('"SEO Lead"', acts[0]["prompt"])


class PauseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "campaign").mkdir()
        (root / "companies" / "a").mkdir(parents=True)
        tick.ROOT, tick.STATE, tick.LOG = root, root / "campaign" / "state.json", root / "campaign" / "log.md"
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def status(self, stage, minutes_ago=300):
        (self.root / "companies" / "a" / "status.json").write_text(json.dumps({"stage": stage, "ts": iso(minutes_ago)}))

    def test_paused_audit_not_nudged_and_nothing_new_started(self):
        st = {"settings": {"max_concurrent_running": 1, "brightdata_paused": True}, "prospects": [
            {"slug": "a", "company": "A", "status": "running", "session_id": "s1"},
            {"slug": "b", "company": "B", "domain": "b.io", "status": "queued"}]}
        self.status("paused_brightdata")
        acts = tick.plan(st, {"s1": {"status_bucket": "idle"}}, NOW)
        self.assertEqual([(a["do"], a.get("status")) for a in acts], [("mark", "paused")])

    def test_resumed_audit_goes_back_to_running(self):
        st = {"settings": {"max_concurrent_running": 1}, "prospects": [
            {"slug": "a", "company": "A", "status": "paused", "session_id": "s1"}]}
        self.status("loop_c", minutes_ago=5)
        acts = tick.plan(st, {"s1": {"status_bucket": "working"}}, NOW)
        self.assertIn(("mark", "running"), [(a["do"], a.get("status")) for a in acts])


class JobExpiryTest(unittest.TestCase):
    def test_stale_job_finds_expire(self):
        st = {"settings": {"max_concurrent_running": 0}, "prospects": [
            {"slug": "old", "company": "O", "status": "proposed", "track": "seo_job", "job": {"posted": "2026-11-05"}},
            {"slug": "new", "company": "N", "status": "queued", "track": "seo_job", "job": {"posted": "2026-11-20"}},
            {"slug": "reg", "company": "R", "status": "proposed"},
            {"slug": "still", "company": "S", "status": "proposed", "track": "seo_job",
             "job": {"posted": "2026-10-20", "open_checked": "2026-11-21"}}]}
        acts = tick.plan(st, {}, NOW)
        self.assertEqual([(a["slug"], a["status"]) for a in acts if a["do"] == "mark"], [("old", "expired")])


if __name__ == "__main__":
    unittest.main()


def test_one_at_a_time_releases_held_approval_before_new_start(tmp_path, monkeypatch):
    import datetime as dt, json
    import tick
    monkeypatch.setattr(tick, "ROOT", tmp_path)
    (tmp_path / "companies").mkdir()
    for slug, stage in (("a", "waiting_gate_1_2"), ("b", "waiting_gate_1_2")):
        (tmp_path / "companies" / slug).mkdir()
        (tmp_path / "companies" / slug / "status.json").write_text(json.dumps({"stage": stage}))
    state = {"settings": {"max_concurrent_running": 1, "one_at_a_time": True}, "prospects": [
        {"slug": "b", "company": "B", "status": "approved_waiting", "session_id": "sb",
         "gate_approval": {"ts": "2026-11-25T14:00:00Z", "sponsor_words": "Approve all"}},
        {"slug": "a", "company": "A", "status": "approved_waiting", "session_id": "sa",
         "gate_approval": {"ts": "2026-11-25T13:00:00Z", "sponsor_words": "Approve all"}},
        {"slug": "c", "company": "C", "status": "queued"}]}
    now = dt.datetime(2026, 11, 25, 15, tzinfo=dt.timezone.utc)
    acts = tick.plan(state, {}, now)
    assert [(x["do"], x["slug"]) for x in acts] == [("release_gate", "a")]
    state["prospects"][1]["status"] = "released"
    assert tick.plan(state, {}, now) == []  # released and still at the gate counts as working: nothing else starts


def test_hold_new_work_until_blocks_release_and_start(tmp_path, monkeypatch):
    import datetime as dt, json
    import tick
    monkeypatch.setattr(tick, "ROOT", tmp_path)
    (tmp_path / "companies" / "a").mkdir(parents=True)
    (tmp_path / "companies" / "a" / "status.json").write_text(json.dumps({"stage": "waiting_gate_1_2"}))
    state = {"settings": {"max_concurrent_running": 1, "one_at_a_time": True,
                          "hold_new_work_until": "2026-11-28T05:00:00Z"},
             "prospects": [{"slug": "a", "company": "A", "status": "approved_waiting", "gate_approval": {"ts": "x"}},
                           {"slug": "c", "company": "C", "status": "queued"}]}
    before = dt.datetime(2026, 11, 27, 12, tzinfo=dt.timezone.utc)
    after = dt.datetime(2026, 11, 28, 6, tzinfo=dt.timezone.utc)
    assert tick.plan(state, {}, before) == []
    assert [x["do"] for x in tick.plan(state, {}, after)] == ["release_gate"]
