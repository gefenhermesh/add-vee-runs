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

    def test_onsite_and_us_based(self):
        self.assertEqual(S.screen(post("us"), "Content Marketing & SEO Specialist (Austin, TX — In Office)")["lean"], "skip")
        self.assertEqual(S.screen(post("us"), "Siana Marketing | Remote (U.S.-based)")["lean"], "skip")
        self.assertEqual(S.screen(post("us"), "Fully remote. Occasional on-site visits optional.")["lean"], "apply")

    def test_seojobs_must_say_remote(self):
        self.assertEqual(S.screen(post("seojobs"), "Join our marketing team in Irving.")["lean"], "skip")
        self.assertEqual(S.screen(post("seojobs"), "This is a remote position.")["lean"], "apply")

    def test_sponsor_feedback_company_is_skipped(self):
        p = post("us"); p["company"] = "Infor"
        r = S.screen(p, "Remote role.")
        self.assertEqual(r["lean"], "skip")
        self.assertIn("sponsor", r["why"][0])

    def test_latam_residence_in_latam_is_fine(self):
        r = S.screen(post("latam"), "Candidates must reside in Latin America.")
        self.assertEqual(r["lean"], "apply")

    def test_real_detail_page(self):
        d = S.description((FX / "li_job_detail_blacksmith.html").read_text(errors="ignore"))
        self.assertIn("Latin America", d)
        self.assertEqual(S.screen(post("us"), d)["lean"], "apply")


class SeojobsPage(unittest.TestCase):
    def test_employer_text_only_and_apply_link(self):
        desc, link = S.seojobs_detail((FX / "seojobs_job_linkedin.html").read_text(errors="ignore"))
        self.assertTrue(desc.startswith("Job Description") or "LinkedIn is the world" in desc[:200])
        self.assertNotIn("Location In-Office", desc)  # the bot's header is left out
        self.assertTrue(link and "apply-click" in link)
        self.assertNotIn("Browse jobs", desc)  # seojobs' sidebar ("Job location: Remote ...") is cut off


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
        self.assertTrue(any("seojobs: not read" in c for c in cov))  # dropped 2026-11-25
        keys = [(p["title"], p["company"]) for p in posts]
        self.assertEqual(len(keys), len(set(keys)))
        cov2, posts2 = S.fetch(now, fetcher=lambda u: page, detail_fetcher=lambda u: detail, paid=lambda u: ("", "x"))
        self.assertEqual(posts2, [])  # nothing new the next run
        md = S.digest("2026-11-24")
        self.assertIn("Apply: https://", md)


if __name__ == "__main__":
    unittest.main()


class GrowthTitleTest(unittest.TestCase):
    def test_growth_title_with_seo_core_is_kept(self):
        d = "Own SEO strategy, technical SEO, AEO and GEO visibility, and organic growth. Fully remote, open to Latin America."
        r = S.screen({"title": "Growth Marketing Manager", "company": "X", "region": "latam", "location": "Brazil"}, d)
        self.assertEqual(r["lean"], "apply")
        self.assertTrue(r["why"][0].startswith("growth/marketing title"))

    def test_growth_title_without_seo_core_is_skipped(self):
        r = S.screen({"title": "Growth Marketing Manager", "company": "X", "region": "latam", "location": "Brazil"},
                          "Paid ads and lifecycle email. Some SEO.")
        self.assertEqual(r["why"], ["not an SEO role"])

    def test_non_search_title_is_not_seo(self):
        r = S.screen({"title": "User Acquisition Manager (Non-search)", "company": "X", "region": "latam", "location": "Brazil"}, "")
        self.assertEqual(r["why"], ["not an SEO role"])


class NoAsiaTest(unittest.TestCase):
    def test_oceania_and_indian_cities_are_skipped(self):
        for loc in ("Sydney, New South Wales, Australia", "Bengaluru, Karnataka", "Auckland, New Zealand"):
            r = S.screen({"title": "SEO Manager", "company": "X", "region": "latam", "location": loc}, "Fully remote.")
            self.assertEqual(r["lean"], "skip", loc)

    def test_ist_hours_in_the_description_are_skipped(self):
        r = S.screen({"title": "Sr. SEO Consultant", "company": "Trantor", "region": "us", "location": "United States"},
                     "Remote. Work Timing: 4:00 PM IST onwards.")
        self.assertEqual(r["why"], ["Asia / Oceania hours or employer"])

