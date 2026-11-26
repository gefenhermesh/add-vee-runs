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
        # sponsor, 2026-11-25: a US post that says nothing about abroad is a maybe, no longer an apply
        self.assertEqual(S.screen(post("us"), "Remote role leading our SEO program.")["lean"], "maybe")
        self.assertEqual(S.screen(post("seojobs"), "")["lean"], "maybe")

    def test_europe_english_is_worth_trying(self):
        self.assertEqual(S.screen(post("europe"), "Remote within Europe.")["lean"], "maybe")  # 2026-11-26: worth trying
        self.assertEqual(S.screen(post("europe"), "We work with contractors worldwide.")["lean"], "apply")
        self.assertEqual(S.screen(post("europe"), "You must have the right to work in the UK.")["lean"], "skip")

    def test_asia_and_junior_are_skipped(self):
        self.assertEqual(S.screen(post("latam", location="Manila, Philippines"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("latam", title="Junior SEO Specialist"), "")["lean"], "skip")

    def test_non_seo_and_loose_phrases(self):
        self.assertEqual(S.screen(post("latam", title="Digital Copywriter"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("latam", title="Practicante de SEO"), "")["lean"], "skip")
        self.assertEqual(S.screen(post("europe", title="Consultant SEO"), "5 ans en agence ou en freelance.")["lean"], "skip")
        self.assertEqual(S.screen(post("europe"), "The editor oversees freelance writers.")["lean"], "maybe")
        self.assertEqual(S.screen(post("europe"), "We serve customers worldwide and across the Americas.")["lean"], "maybe")
        self.assertEqual(S.screen(post("us"), "This role is remote and open to candidates worldwide.")["lean"], "apply")

    def test_onsite_and_us_based(self):
        self.assertEqual(S.screen(post("us"), "Content Marketing & SEO Specialist (Austin, TX — In Office)")["lean"], "skip")
        self.assertEqual(S.screen(post("us"), "Siana Marketing | Remote (U.S.-based)")["lean"], "skip")
        self.assertEqual(S.screen(post("us"), "Fully remote. Occasional on-site visits optional.")["lean"], "maybe")

    def test_seojobs_must_say_remote(self):
        self.assertEqual(S.screen(post("seojobs"), "Join our marketing team in Irving.")["lean"], "skip")
        self.assertEqual(S.screen(post("seojobs"), "This is a remote position.")["lean"], "maybe")

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


class UsTraditionalTest(unittest.TestCase):
    """Sponsor, 2026-11-25: authorization is asked in the form, so silence means nothing; only startups and agencies
    are worth a maybe in the US without a positive sign."""
    def p(self, company, location="United States"):
        return {"title": "SEO Manager", "company": company, "region": "us", "location": location}

    def test_traditional_and_staffing_are_skipped(self):
        self.assertEqual(S.screen(self.p("Nordstrom", "New York, NY"), "Across all touchpoints, from our stores.")["lean"], "skip")
        self.assertEqual(S.screen(self.p("Acme Staffing"), "Remote.")["lean"], "skip")

    def test_agency_is_worth_trying(self):
        r = S.screen(self.p("Bright Owl", "Austin, TX"), "We are a digital agency helping B2B brands. Remote.")
        self.assertEqual(r["lean"], "apply")  # worth trying even if the form asks (sponsor, 2026-11-25)

    def test_unknown_type_is_left_to_the_scout(self):
        r = S.screen(self.p("Zorblax", "Denver, CO"), "Remote role.")
        self.assertEqual(r["lean"], "maybe")
        self.assertTrue(r.get("needs_kind"))

    def test_positive_sign_still_applies(self):
        self.assertEqual(S.screen(self.p("Zorblax", "San Francisco, CA"), "Remote, open to contractors in Latin America.")["lean"], "apply")


class LanguageTest(unittest.TestCase):
    def test_foreign_language_european_post_is_skipped(self):
        de = ("Wir suchen für unser Team in Berlin eine erfahrene Person für SEO und GEO. Du arbeitest mit dem Content Team "
              "und bist für die Sichtbarkeit unserer Marke verantwortlich. Wir bieten dir ein tolles Team und flexible Arbeitszeiten "
              "mit der Möglichkeit, remote zu arbeiten, und eine Vergütung, die zu deiner Erfahrung passt.")
        r = S.screen({"title": "SEO Manager (m/w/d)", "company": "X", "region": "europe", "location": "Germany"}, de)
        self.assertEqual(r["why"], ["post not in English or Spanish"])

    def test_title_marker_without_description(self):
        self.assertTrue(S.foreign_language("Senior SEO Manager (m/w/d)", ""))
        self.assertFalse(S.foreign_language("Senior SEO Manager", ""))

    def test_low_end_jobs_are_ok_for_now(self):
        r = S.screen({"title": "SEO Implementation Specialist (WordPress)", "company": "X", "region": "latam", "location": "Brazil"}, "Fully remote.")
        self.assertNotEqual(r["lean"], "skip")

    def test_portuguese_is_foreign_spanish_is_not(self):
        pt = "Estamos buscando uma pessoa para o nosso time de SEO. Você vai trabalhar com a equipe de conteúdo e ter autonomia para crescer."
        es = "Buscamos una persona para nuestro equipo de SEO. Vas a trabajar con el equipo de contenido de forma remota desde LATAM."
        self.assertTrue(S.foreign_language("Analista de SEO", pt))
        self.assertFalse(S.foreign_language("Especialista SEO", es))



def test_linkedin_post_in_a_city_that_never_says_remote_is_skipped():
    # Sponsor, 2026-11-26: Kanbar Digital (San Diego) came through LinkedIn's remote search but is hybrid.
    import seeker
    post = {"title": "SEO Manager", "company": "Kanbar Digital, LLC", "location": "San Diego, CA", "region": "us"}
    desc = ("Job Purpose: To support and execute on-page and off-page optimization strategies to improve website "
            "visibility and drive organic traffic. Manage and support 5-8 clients. Conduct keyword research.")
    r = seeker.screen(post, desc)
    assert r["lean"] == "skip" and "never says remote" in r["why"][0]
    post2 = dict(post, location="United States")
    assert "never says remote" not in " ".join(seeker.screen(post2, desc)["why"])
