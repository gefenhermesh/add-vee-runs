"""Offline tests for the scout readers, on saved pages. Run: python -m unittest campaign/scout/test_readers.py"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import readers as R  # noqa: E402

FX = HERE / "fixtures"


class ReaderTest(unittest.TestCase):
    def test_firgun(self):
        leads = R.parse_firgun((FX / "firgun_2026-11-13.html").read_text(errors="ignore"))
        by = {l["company"]: l for l in leads}
        self.assertIn("Daylight Security", by)
        self.assertEqual(by["Daylight Security"]["amount_musd"], 80)
        self.assertEqual(by["Daylight Security"]["stage"].lower(), "series b")
        self.assertIn("Bay", by)
        self.assertIn("Yuval Zacharia", by["Bay"]["founders"])
        self.assertEqual(by["Dreeze"]["stage"].lower(), "seed")
        self.assertEqual(by["Ribon"]["note"], "still in stealth")

    def test_telegram(self):
        leads = R.parse_telegram_jobs((FX / "tg_marketing.html").read_text(errors="ignore"))
        self.assertGreater(len(leads), 20)
        l = next(x for x in leads if x["company"] == "Buildots")
        self.assertIn("Marketing", l["role"])
        self.assertEqual(l["location"], "Tel Aviv")
        self.assertTrue(l["date"].startswith("2026-"))

    def test_avi_list(self):
        leads = R.parse_avi_list((FX / "avi_post.html").read_text(errors="ignore"))
        by = {l["company"]: l for l in leads}
        self.assertEqual(len(leads), 23)
        self.assertEqual(by["Sentra"]["amount_musd"], 150)
        self.assertEqual(by["Sentra"]["open_roles"], 11)
        self.assertEqual(by["Pluto Security"]["open_roles"], 1)
        self.assertIsNone(by["Capitolis"]["open_roles"])

    def test_ashby(self):
        p = R.parse_job_board("ashby", (FX / "ashby_bay.json").read_text())
        self.assertEqual(p["open_roles"], 9)
        self.assertEqual(p["marketing_roles"], [])



class NewReaderTest(unittest.TestCase):
    def test_ctech_appointments(self):
        leads = R.parse_ctech_appointments((FX / "ctech_appointments_rendered.html").read_text(errors="ignore"))
        by = {l["company"]: l for l in leads}
        self.assertTrue(by["Terra Security"]["marketing_leader_hire"])
        self.assertEqual(by["Buildots"]["role"], "Chief Revenue Officer")
        self.assertFalse(by["Buildots"]["marketing_leader_hire"])
        self.assertEqual(by["Terra Security"]["date"], "2026-11-05")

    def test_ctech_startups(self):
        leads = R.parse_ctech_startups((FX / "ctech_startups_rendered.html").read_text(errors="ignore"))
        by = {l["company"]: l for l in leads if l["company_known"]}
        self.assertEqual(by["Ramon.Space"]["amount_musd"], 124)
        self.assertTrue(any("Vero" in l["raw"] for l in leads))  # company only in the teaser: kept raw for the scout

    def test_nextplay_feed(self):
        leads = R.parse_nextplay_feed((FX / "nextplay_feed.xml").read_text(errors="ignore"))
        names = {l["company"] for l in leads}
        self.assertIn("MIND", names)          # list post line
        self.assertIn("Genesis Computing", names)  # "Should you join"
        self.assertTrue(any(l["signal"] == "hiring" and l.get("role") for l in leads))

    def test_avi_recent_activity(self):
        leads = R.parse_avi_list((FX / "avi_recent_activity.html").read_text(errors="ignore"))
        self.assertEqual(len(leads), 23)


class GeneralFeedTest(unittest.TestCase):
    def test_techcrunch_fundraising(self):
        leads = R.parse_rss_funding((FX / "techcrunch_fundraising.xml").read_text(errors="ignore"), "techcrunch_fundraising")
        self.assertTrue(leads)
        self.assertTrue(all(l["signal"] == "funding" and l["amount_musd"] for l in leads))
        self.assertTrue(any(l["company_known"] for l in leads))


class LinkedInDatasetTest(unittest.TestCase):
    def test_jobs(self):
        import json
        leads = R.parse_li_jobs(json.loads((FX / "li_jobs_marketing_israel.json").read_text()))
        self.assertGreater(len(leads), 10)
        self.assertTrue(any(l["company"] == "Wix" and l["seo_role"] for l in leads))  # "organic growth marketer"

    def test_avi_posts(self):
        import json
        leads = R.parse_avi_posts(json.loads((FX / "li_posts_avi.json").read_text()))
        self.assertEqual(len(leads), 23)
        self.assertEqual({l["company"] for l in leads} >= {"Sentra", "Bay"}, True)


if __name__ == "__main__":
    unittest.main()
