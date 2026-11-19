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


if __name__ == "__main__":
    unittest.main()
