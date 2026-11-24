"""Tests for campaign/scout/seeker.py. Run: python -m unittest campaign/scout/test_seeker.py"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seeker as S  # noqa: E402

FX = HERE / "fixtures"


def post(region, title="SEO Manager", location="Remote"):
    return {"region": region, "title": title, "location": location, "company": "Acme", "job_id": "1"}


class Screen(unittest.TestCase):
    def test_us_authorization_is_skipped(self):
        r = S.screen(post("us"), "You must be authorized to work in the United States. No visa sponsorship.")
        self.assertEqual(r["lean"], "skip")
        self.assertTrue(r["quotes"])

    def test_us_open_to_latam_is_apply(self):
        r = S.screen(post("us"), "Fully remote. We hire across the Americas as independent contractors.")
        self.assertEqual(r["lean"], "apply")

    def test_us_unstated_is_apply_but_unread_is_maybe(self):
        self.assertEqual(S.screen(post("us"), "Remote role leading our SEO program.")["lean"], "apply")
        self.assertEqual(S.screen(post("seojobs"), "")["lean"], "maybe")

    def test_europe_needs_a_positive_signal(self):
        self.assertEqual(S.screen(post("europe"), "Remote within Europe.")["lean"], "skip")
        self.assertEqual(S.screen(post("europe"), "We work with contractors worldwide.")["lean"], "apply")
        self.assertEqual(S.screen(post("europe"), "You must have the right to work in the UK.")["lean"], "skip")

    def test_asia_and_junior_are_skipped(self):
        self.assertEqual(S.screen(post("latam", location="Manila, Philippines"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("latam", title="Junior SEO Specialist"), "")["lean"], "skip")

    def test_non_seo_and_loose_phrases(self):
        self.assertEqual(S.screen(post("latam", title="Digital Copywriter"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("latam", title="Practicante de SEO"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("europe", title="Consultant SEO"), "5 ans en agence ou en freelance.")["lean"], "skip")
        self.assertEqual(S.screen(post("europe"), "The editor oversees freelance writers.")["lean"], "skip")
        self.assertEqual(S.screen(post("europe"), "We serve customers worldwide and across the Americas.")["lean"], "skip")
        self.assertEqual(S.screen(post("us"), "This role is remote and open to candidates worldwide.")["lean"], "apply")

    def test_latam_residence_in_latam_is_fine(self):
        r = S.screen(post("latam"), "Candidates must reside in Latin America.")
        self.assertEqual(r["lean"], "apply")

    def test_real_detail_page(self):
        d = S.description((FX / "li_job_detail_blacksmith.html").read_text(errors="ignore"))
        self.assertIn("Latin America", d)
        self.assertEqual(S.screen(post("us"), d)["lean"], "apply")


class FetchAndDigest(unittest.TestCase):
    def test_fetch_dedupes_and_writes_digest(self):
        tmp = Path(tempfile.mkdtemp())
        S.OUT, S.SEEN = tmp, tmp / "seen.jsonl"
        page = (FX / "li_seeker_latam_remote.html").read_text(errors="ignore")
        detail = (FX / "li_job_detail_blacksmith.html").read_text(errors="ignore")
        now = dt.datetime(2026, 11, 24, 12, tzinfo=dt.timezone.utc)
        S.time.sleep = lambda s: None
        cov, posts = S.fetch(now, fetcher=lambda u: page, detail_fetcher=lambda u: detail,
                             paid=lambda u: ("", "dry_run"))
        self.assertTrue(any("seojobs: FAILED" in c for c in cov))
        keys = [(p["title"], p["company"]) for p in posts]
        self.assertEqual(len(keys), len(set(keys)))
        cov2, posts2 = S.fetch(now, fetcher=lambda u: page, detail_fetcher=lambda u: detail, paid=lambda u: ("", "x"))
        self.assertEqual(posts2, [])  # nothing new the next run
        md = S.digest("2026-11-24")
        self.assertIn("Apply: https://", md)


if __name__ == "__main__":
    unittest.main()
