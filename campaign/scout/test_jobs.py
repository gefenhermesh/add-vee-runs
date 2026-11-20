"""Tests for campaign/scout/jobs.py. Run: python -m pytest -q campaign/scout/test_jobs.py"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jobs  # noqa: E402


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        jobs.SEEN, jobs.COMPANIES = d / "seen.jsonl", d / "companies.json"
        self.us = jobs.parse((HERE / "fixtures" / "li_jobs_seo_us.html").read_text(errors="ignore"), "us")
        self.eu = jobs.parse((HERE / "fixtures" / "li_jobs_seo_europe.html").read_text(errors="ignore"), "europe")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse(self):
        self.assertGreaterEqual(len(self.us), 50)
        self.assertGreaterEqual(len(self.eu), 50)
        first = self.us[0]
        self.assertEqual(first["company"], "Keeper Security, Inc.")
        self.assertEqual(first["company_key"], "keeper-security-inc-")
        self.assertTrue(first["url"].startswith("https://www.linkedin.com/jobs/view/"))
        self.assertEqual(first["posted"], "2026-11-20")

    def test_store_only_new(self):
        t = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
        new1 = jobs.store(self.us, t)
        self.assertTrue(new1)
        new2 = jobs.store(self.us + self.eu, t + dt.timedelta(days=1))
        keys1 = {c["key"] for c in new1}
        self.assertTrue(all(c["key"] not in keys1 for c in new2))  # US companies aren't new the next day
        lines = jobs.SEEN.read_text().splitlines()
        self.assertEqual(len(lines), len({json.loads(l)["job_id"] for l in lines}))  # no duplicate posts

    def test_classify_and_startups(self):
        t = dt.datetime.now(dt.timezone.utc)
        new = jobs.store(self.us, t)
        f = Path(self.tmp.name) / "c.json"
        f.write_text(json.dumps([{"key": new[0]["key"], "class": "startup", "why": "Series B SaaS"}]))
        jobs.main(["classify", str(f)])
        self.assertEqual(json.loads(jobs.COMPANIES.read_text())[new[0]["key"]]["class"], "startup")
        f.write_text(json.dumps([{"key": new[1]["key"], "class": "startup"}]))
        with self.assertRaises(SystemExit):  # a reason is required
            jobs.main(["classify", str(f)])


if __name__ == "__main__":
    unittest.main()
