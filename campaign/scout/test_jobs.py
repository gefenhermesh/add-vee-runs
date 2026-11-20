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


    def test_extra_sources(self):
        now = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
        wf = jobs.parse_wellfound((HERE / "fixtures" / "wellfound_seo_specialist.html").read_text(errors="ignore"), now=now)
        self.assertTrue(wf)
        self.assertTrue(all(jobs.SEO_TITLE.search(p["title"]) for p in wf))
        self.assertTrue(all(p["posted"] >= "2026-10-30" for p in wf))      # old listings dropped
        self.assertTrue(any(p.get("size") for p in wf))
        sj = jobs.parse_seojobs((HERE / "fixtures" / "seojobs_jobs.html").read_text(errors="ignore"), now=now)
        names = {p["company"] for p in sj}
        self.assertIn("AVILOO", names)
        self.assertIn("LinkedIn", names)  # not "LinkedIn | $170,000"
        self.assertTrue(all(p["posted"] >= "2026-11-17" for p in sj))

    def test_same_company_across_sources(self):
        t = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
        jobs.store([{"job_id": "1", "title": "SEO Lead", "company": "Acme, Inc.", "company_url":
                     "https://www.linkedin.com/company/acme-io", "company_key": "acme-io", "location": "NYC",
                     "posted": "2026-11-20", "url": "u1", "region": "us"}], t)
        new = jobs.store([{"job_id": "sj-2", "title": "SEO Manager", "company": "ACME", "company_url": None,
                           "company_key": "name:acme", "location": "NYC", "posted": "2026-11-20", "url": "u2",
                           "region": "seojobs"}], t)
        self.assertEqual(new, [])
        self.assertEqual(len(json.loads(jobs.COMPANIES.read_text())["acme-io"]["posts"]), 2)


if __name__ == "__main__":
    unittest.main()
