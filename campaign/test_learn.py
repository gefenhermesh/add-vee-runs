"""Tests for campaign/learn.py. Run: python -m unittest campaign/test_learn.py"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import learn  # noqa: E402

AT = dt.datetime(2026, 12, 31, tzinfo=dt.timezone.utc)


def rec(slug, cls=None, days_ago=20, **features):
    return {"slug": slug, "sent_at": (AT - dt.timedelta(days=days_ago)).isoformat(),
            "features": features, "outcome": {"class": cls} if cls else {}}


class LearnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        learn.LOG = root / "outreach_log.jsonl"
        learn.REPORT = root / "learnings.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_settling_rules(self):
        self.assertTrue(learn.settled(rec("a", "positive", days_ago=1), AT))
        self.assertFalse(learn.settled(rec("b", None, days_ago=5), AT))
        self.assertTrue(learn.settled(rec("c", None, days_ago=15), AT))
        self.assertFalse(learn.settled(rec("d", "auto", days_ago=2), AT))  # out-of-office isn't an answer

    def test_rates_use_settled_only_and_count_negative_as_reply(self):
        rows = [rec("a", "positive", industry="devtools"), rec("b", "negative", industry="devtools"),
                rec("c", None, industry="devtools"), rec("d", None, days_ago=3, industry="devtools")]
        s = learn.stats(rows, AT)
        k, n = s["overall"][:2]
        self.assertEqual((k, n), (2, 3))
        kp, npos = learn.stats(rows, AT, positive_only=True)["overall"][:2]
        self.assertEqual((kp, npos), (1, 3))

    def test_report_marks_small_cells_too_early(self):
        rows = [rec("a", "positive", industry="fintech"), rec("b", None, industry="security"),
                rec("c", None, industry="security"), rec("d", "neutral", industry="security")]
        text = learn.render(rows, AT)
        self.assertIn("fintech *(too early)*", text)
        self.assertIn("| security | 1/3 |", text)

    def test_pick_reserves_exploration_and_prefers_winners(self):
        rows = [rec(f"w{i}", "positive", industry="devtools") for i in range(6)] + \
               [rec(f"l{i}", None, industry="security") for i in range(6)]
        cands = [{"slug": f"dev{i}", "features": {"industry": "devtools"}} for i in range(4)] + \
                [{"slug": f"sec{i}", "features": {"industry": "security"}} for i in range(4)] + \
                [{"slug": "fin0", "features": {"industry": "fintech"}}]
        picks = learn.pick(rows, cands, 5, AT, seed=1)
        whys = {p["slug"]: p["why_picked"] for p in picks}
        self.assertEqual(whys.get("fin0"), "explore")  # never tried: explored
        exploit = [s for s, w in whys.items() if w == "exploit"]
        self.assertTrue(all(s.startswith("dev") for s in exploit))  # winners exploited

    def test_warmup_is_a_mix_with_a_remote_first_pick(self):
        cands = [{"slug": f"sec{i}", "features": {"industry": "security", "stage": "series_a", "remote_hiring": "office"}}
                 for i in range(5)] + \
                [{"slug": "fin", "features": {"industry": "fintech", "stage": "series_b", "remote_hiring": "remote_us_only"}},
                 {"slug": "hr", "features": {"industry": "hr_tech", "stage": "seed", "remote_hiring": "remote_global"}},
                 {"slug": "dev", "features": {"industry": "devtools", "stage": "series_c_plus", "remote_hiring": "office"}}]
        picks = learn.pick([], cands, 4, AT, seed=2)  # no replies yet: warm-up
        whys = {p["slug"]: p["why_picked"] for p in picks}
        self.assertEqual(whys.get("hr"), "remote_first")
        industries = [next(c for c in cands if c["slug"] == s)["features"]["industry"] for s in whys]
        self.assertEqual(len(industries), len(set(industries)))  # four picks, four different industries
        self.assertTrue(all(w in ("mix", "remote_first") for w in whys.values()))

    def test_add_rejects_untracked_feature(self):
        f = Path(self.tmp.name) / "r.json"
        f.write_text('{"slug":"x","sent_at":"2026-12-01T00:00:00+00:00","features":{"vibes":"good"}}')
        with self.assertRaises(SystemExit):
            learn.main(["add", str(f)])


if __name__ == "__main__":
    unittest.main()
