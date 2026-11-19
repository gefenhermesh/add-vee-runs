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


if __name__ == "__main__":
    unittest.main()
