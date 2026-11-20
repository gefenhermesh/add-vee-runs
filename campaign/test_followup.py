"""Tests for campaign/followup.py. Run: python -m pytest -q campaign/test_followup.py"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import followup as F  # noqa: E402

MON = "2026-11-23T09:00:00+00:00"  # a Monday


def run(*args, at=MON):
    buf = io.StringIO()
    with redirect_stdout(buf):
        F.main(["--at", at, *args])
    out = buf.getvalue().strip()
    try:
        return json.loads(out)
    except ValueError:
        return out


class FollowupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "campaign").mkdir()
        F.ROOT, F.STATE, F.LOG = root, root / "campaign" / "state.json", root / "campaign" / "log.md"
        F.STATE.write_text(json.dumps({"prospects": [{"slug": "acme", "company": "Acme", "domain": "acme.io",
                                                      "branch": "campaign/acme"}]}))
        F.LOG.write_text("# log\n\n## Ticks\n\n## Cohorts\n")

    def tearDown(self):
        self.tmp.cleanup()

    def send1(self, email="ceo@acme.io", at=MON):
        return run("sent", "acme", "--email", email, "--contact", "Dana", "--role", "CEO",
                   "--thread", "T1", "--message", "M1", at=at)["thread"]

    def test_gap_in_business_days(self):
        tid = self.send1()
        self.assertEqual(run("due", at="2026-11-26T09:00:00+00:00"), [])          # Thu: 3 business days
        d = run("due", at="2026-11-27T09:00:00+00:00")                            # Fri: 4 business days
        self.assertEqual([x["key"] for x in d], [tid])

    def test_israeli_weekend(self):
        run("sent", "acme", "--email", "a@acme.io", "--contact", "A", "--role", "CMO", "--thread", "T",
            "--message", "M", "--weekend", "fri,sat", at="2026-11-19T09:00:00+00:00")  # Thu
        # Fri, Sat skipped: Sun 22, Mon 23, Tue 24, Wed 25 = 4
        self.assertEqual(run("due", at="2026-11-24T09:00:00+00:00"), [])
        self.assertEqual(len(run("due", at="2026-11-25T09:00:00+00:00")), 1)

    def test_full_sequence_then_committee(self):
        tid = self.send1()
        fri = "2026-11-27T09:00:00+00:00"
        run("start", "acme", tid, "--session", "S1", at=fri)
        self.assertEqual(run("due", at=fri), [])                                   # pending blocks
        run("decided", "acme", tid, "--decision", "send", "--type", "V", "--draft-id", "D1", at=fri)
        self.assertEqual(run("due", at="2026-12-07T09:00:00+00:00"), [])          # open draft blocks
        run("step-sent", "acme", tid, "--message", "M2", at="2026-11-30T10:00:00+00:00")
        self.assertEqual(len(run("due", at="2026-12-04T09:00:00+00:00")), 1)
        run("decided", "acme", tid, "--decision", "send", "--type", "N", "--draft-id", "D2", at="2026-12-04T09:00:00+00:00")
        run("step-sent", "acme", tid, "--message", "M3", at="2026-12-07T10:00:00+00:00")
        d = run("due", at="2026-12-11T09:00:00+00:00")
        self.assertEqual([x["key"] for x in d], ["committee"])                     # person 1 exhausted
        with self.assertRaises(SystemExit):
            run("decided", "acme", tid, "--decision", "send", "--type", "L", at="2026-12-11T09:00:00+00:00")
        run("decided", "acme", "committee", "--decision", "send", "--draft-id", "D3", at="2026-12-11T09:00:00+00:00")
        self.assertEqual(run("due", at="2026-12-18T09:00:00+00:00"), [])          # committee draft blocks
        run("sent", "acme", "--email", "cmo@acme.io", "--contact", "Lee", "--role", "CMO", "--thread", "T2",
            "--message", "M4", "--kind", "committee", "--at-sent", "2026-12-14T10:00:00+00:00", at="2026-12-14T10:00:00+00:00")
        d = run("due", at="2026-12-18T09:00:00+00:00")
        self.assertEqual([x["key"] for x in d], ["acme/2"])
        with self.assertRaises(SystemExit):                                         # no third person
            run("sent", "acme", "--email", "x@acme.io", "--contact", "X", "--role", "VP", "--thread", "T3",
                "--message", "M5", at="2026-12-20T10:00:00+00:00")

    def test_reply_stops_company_and_ooo_defers(self):
        tid = self.send1()
        r = run("reply", "acme", tid, "--class", "ooo", "--until", "2026-12-10T00:00:00+00:00")
        self.assertFalse(r["notify_sponsor_now"])
        self.assertEqual(run("due", at="2026-12-01T09:00:00+00:00"), [])
        self.assertEqual(len(run("due", at="2026-12-10T09:00:00+00:00")), 1)
        r = run("reply", "acme", tid, "--class", "positive")
        self.assertTrue(r["notify_sponsor_now"])
        self.assertEqual(run("due", at="2026-12-20T09:00:00+00:00"), [])
        with self.assertRaises(SystemExit):
            run("decided", "acme", tid, "--decision", "send", "--type", "V")

    def test_one_email_per_company_per_day(self):
        self.send1()
        with self.assertRaises(SystemExit):
            run("sent", "acme", "--email", "cmo@acme.io", "--contact", "L", "--role", "CMO", "--thread", "T2",
                "--message", "M", "--at-sent", "2026-11-23T15:00:00+00:00")

    def test_prompt_and_pending(self):
        tid = self.send1()
        run("start", "acme", tid, "--session", "S9", at="2026-11-27T09:00:00+00:00")
        p = run("pending", at="2026-11-28T12:00:00+00:00")
        self.assertTrue(p[0]["stale"])
        text = run("prompt", "acme", tid)
        self.assertIn("docs/campaign/followup-strategist.md", text)
        self.assertIn("output/acme/followups/1-1/", text)


if __name__ == "__main__":
    unittest.main()
