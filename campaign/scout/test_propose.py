"""Tests for campaign/scout/propose.py. Run: python -m unittest campaign/scout/test_propose.py"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import propose  # noqa: E402
import learn  # noqa: E402


def good():
    return {"scout_version": 2, "company": "X", "domain": "x.io", "reason": "Fresh Series A; marketing lead, no SEO.",
            "gating_rating": "sweet_spot", "features": {f: "v" for f in learn.FEATURES},
            "contacts": [{"name": "A B", "role": "VP Marketing"}],
            "sources": [{"url": "https://x.io", "date": "2026-11-20", "kind": "direct"}]}


class ProposeTest(unittest.TestCase):
    def test_good_record_passes(self):
        self.assertEqual(propose.problems(good()), [])

    def test_missing_feature_and_bad_source(self):
        r = good()
        del r["features"]["industry"]
        r["sources"] = [{"url": "https://x.io"}]
        p = propose.problems(r)
        self.assertTrue(any("industry" in x for x in p))
        self.assertTrue(any("source needs" in x for x in p))

    def test_seo_team_blocks(self):
        r = good()
        r["gating_rating"] = "blocked_seo_team"
        self.assertTrue(any("blocked" in x for x in propose.problems(r)))

    def test_v3_needs_seo_need(self):
        r = good()
        r["scout_version"] = 3
        self.assertTrue(any("seo_need.rating" in x for x in propose.problems(r)))
        r["seo_need"] = {"rating": "medium", "buyer_research": "mixed", "competitors": [{"name": "Y"}],
                         "cost_of_absence": "new line has no page", "why_not_yet": "never_prioritized"}
        r["features"]["seo_need"] = "medium"
        self.assertEqual(propose.problems(r), [])
        r["seo_need"]["rating"] = r["features"]["seo_need"] = "low"
        self.assertTrue(any("low SEO need" in x for x in propose.problems(r)))

    def test_pick_caps_non_b2b(self):
        cands = [{"slug": f"c{i}", "b2b": i >= 4, "features": {"industry": f"x{i}"}} for i in range(8)]
        for _ in range(20):
            picks = propose.capped_pick([], cands, 5, learn.now())
            self.assertEqual(len(picks), 5)
            self.assertLessEqual(sum(not c["b2b"] for c in picks), 1)

    def test_v4_needs_game_changer(self):
        r = good()
        r["scout_version"] = 4
        r["seo_need"] = {"rating": "high", "buyer_research": "online", "competitors": [{"name": "Y"}],
                         "cost_of_absence": "c", "why_not_yet": "never_prioritized"}
        r["features"]["seo_need"] = "high"
        self.assertTrue(any("game_changer" in x for x in propose.problems(r)))
        r["game_changer"] = {"verdict": "yes", "why": "losing shortlists to a named rival right after a round"}
        self.assertEqual(propose.problems(r), [])


if __name__ == "__main__":
    unittest.main()
