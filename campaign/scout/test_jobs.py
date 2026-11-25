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
        jobs.SEEN, jobs.COMPANIES, jobs.SOURCE_STATE = d / "seen.jsonl", d / "companies.json", d / "sources.json"
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
        t = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)  # the fixture's day: store() keeps only fresh posts
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


    def test_getro_and_berlin(self):
        now = dt.datetime(2026, 11, 21, 12, tzinfo=dt.timezone.utc)
        g = jobs.parse_getro((HERE / "fixtures" / "getro_accel_seo.html").read_text(errors="ignore"), now=now, board="accel")
        self.assertTrue(g)
        self.assertTrue(all(p["stage"] not in jobs.LATE_STAGES for p in g))       # Klaviyo (IPO), Fever (PE) dropped
        self.assertNotIn("Klaviyo", {p["company"] for p in g})
        b = jobs.parse_berlin((HERE / "fixtures" / "berlinstartupjobs_seo.html").read_text(errors="ignore"))
        self.assertIn("Scento", {p["company"] for p in b})

    def test_only_what_changed(self):
        page = (HERE / "fixtures" / "berlinstartupjobs_seo.html").read_text(errors="ignore")
        fetch = lambda url: (page, None)
        now = dt.datetime(2026, 11, 21, 8, tzinfo=dt.timezone.utc)
        cov, posts = jobs.run_sources(fetch, now, only=["berlinstartupjobs"])
        self.assertTrue(posts)
        jobs.store(posts, now)
        cov, posts = jobs.run_sources(fetch, now + dt.timedelta(days=1), only=["berlinstartupjobs"])
        self.assertEqual(posts, [])
        self.assertIn("unchanged", cov[0])
        cov, _ = jobs.run_sources(lambda url: ("", "dd_hardblock"), now, only=["berlinstartupjobs"])
        self.assertIn("FAILED", cov[0])


class CostTest(unittest.TestCase):
    """Free reads first, paid only on refusal, quiet sources checked less often (sponsor, 2026-11-20)."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        jobs.SEEN, jobs.COMPANIES, jobs.SOURCE_STATE = d / "seen.jsonl", d / "companies.json", d / "sources.json"
        self.page = (HERE / "fixtures" / "li_jobs_seo_us.html").read_text(errors="ignore")
        self.paid = []

    def tearDown(self):
        self.tmp.cleanup()

    def paid_fetch(self, url):
        self.paid.append(url)
        return self.page, None

    def test_direct_read_costs_nothing(self):
        now = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
        cov, posts = jobs.run_sources(self.paid_fetch, now, only=["linkedin_us"], direct=lambda u: self.page)
        self.assertEqual(self.paid, [])
        self.assertTrue(posts and "(direct)" in cov[0])

    def test_paid_only_when_direct_refused(self):
        now = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)

        def refuse(url):
            raise OSError("403")
        cov, posts = jobs.run_sources(self.paid_fetch, now, only=["linkedin_us"], direct=refuse)
        self.assertEqual(len(self.paid), 1)
        self.assertIn("(unlocker)", cov[0])

    def test_every_source_is_read_daily(self):
        """Sponsor, 2026-11-25: no back-off; an unchanged source is still read the next day."""
        t = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
        pg = (HERE / "fixtures" / "berlinstartupjobs_seo.html").read_text(errors="ignore")
        same = lambda u: pg
        jobs.SOURCES_SAVED = jobs.SOURCES
        jobs.SOURCES = {"berlinstartupjobs": jobs.SOURCES_SAVED["berlinstartupjobs"]}
        try:
            jobs.run_sources(self.paid_fetch, t, None, direct=same)
            for day in (1, 2, 3):
                cov, _ = jobs.run_sources(self.paid_fetch, t + dt.timedelta(days=day, minutes=-30), None, direct=same)
                self.assertIn("next check in 1 days", cov[0])
            self.assertEqual(self.paid, [])
        finally:
            jobs.SOURCES = jobs.SOURCES_SAVED

    def test_telegram_seo_titles_only(self):
        page = ('<div class="tgme_widget_message_text js-message_text">🔹 Senior SEO &amp; GEO Specialist<br/>🏢 DealHub · 📍 Holon</div>'
                '<time datetime="2026-11-16T10:00:00+00:00"></time>'
                '<div class="tgme_widget_message_text js-message_text">🔹 User Acquisition Manager (Non-search)<br/>🏢 W · 📍 Tel Aviv</div>'
                '<time datetime="2026-11-19T10:00:00+00:00"></time>')
        got = jobs.parse_telegram(page)
        self.assertEqual([p["title"] for p in got], ["Senior SEO & GEO Specialist"])
        self.assertEqual(got[0]["region"], "telegram_il")

    def test_linkedin_window_widens_after_missed_day(self):
        t = dt.datetime(2026, 11, 20, 8, tzinfo=dt.timezone.utc)
        prev = {"checked": (t - dt.timedelta(days=3)).isoformat()}
        self.assertIn("f_TPR=r262800", jobs.source_url("linkedin_us", "", prev, t))   # 3 days + 1 h
        self.assertIn("f_TPR=r86400", jobs.source_url("linkedin_us", "", {"checked": (t - dt.timedelta(hours=20)).isoformat()}, t))

    def test_unlocker_cap(self):
        import readers as R
        d = Path(self.tmp.name)
        R._USAGE, R._BUDGET = d / "u.jsonl", d / "b.json"
        R._BUDGET.write_text(json.dumps({"unlocker_requests_per_week": 2}))
        R.log_unlocker("t", "u1")
        R.log_unlocker("t", "u2")
        self.assertEqual(R.bd_usage_this_week(), (0, 0))          # dataset budget untouched
        with self.assertRaises(RuntimeError):
            R.unlocker_check("third")


    def test_no_backlog_old_posts_recorded_not_triaged(self):
        now = dt.datetime(2026, 11, 21, 8, tzinfo=dt.timezone.utc)
        mk = lambda i, posted, base=False: {"job_id": f"j{i}", "title": "SEO Lead", "company": f"Co{i}", "company_url": None,
                                            "company_key": f"name:co{i}", "location": "NYC", "posted": posted, "url": f"u{i}",
                                            "region": "us", "baseline": base}
        out = jobs.store([mk(1, "2026-11-20"), mk(2, "2026-11-05"), mk(3, None, base=True), mk(4, None)], now)
        self.assertEqual({c["name"] for c in out}, {"Co1", "Co4"})   # fresh dated post; undated post on a known source
        self.assertEqual(jobs.store.recorded_only, 2)                 # old post and first-read undated post: recorded only
        names = [r[1]["name"] for r in jobs.backlog_rows(json.loads(jobs.COMPANIES.read_text()))]
        self.assertEqual(names, ["Co2", "Co3"])                        # ...but kept in the backlog, newest post first
        # Co2 (recorded, never classified) posts a fresh role later: offered once
        out = jobs.store([{**mk(5, "2026-11-21"), "company": "Co2", "company_key": "name:co2"}], now)
        self.assertEqual([c["name"] for c in out], ["Co2"])
        out = jobs.store([{**mk(6, "2026-11-21"), "company": "Co2", "company_key": "name:co2"}], now)
        self.assertEqual(out, [])                                     # already offered: not again
        self.assertNotIn("Co2", [r[1]["name"] for r in jobs.backlog_rows(json.loads(jobs.COMPANIES.read_text()))])


class OpenCheckTest(unittest.TestCase):
    """Is the role still available? The company's own board decides (sponsor, 2026-11-23)."""

    def fake(self, pages):
        def fetch(url):
            for k, v in pages.items():
                if k in url:
                    if isinstance(v, Exception):
                        raise v
                    return v
            raise OSError("not found")
        return fetch

    def test_listed_on_company_board_is_open(self):
        f = self.fake({"linkedin.com/jobs/view/1": "<html>Apply now</html>",
                       "acme.io/careers": '<a href="https://jobs.ashbyhq.com/acme-inc">Jobs</a>',
                       "api.ashbyhq.com/posting-api/job-board/acme-inc": '{"jobs":[{"title":"Senior SEO Manager"}]}'})
        r = jobs.open_check("https://www.linkedin.com/jobs/view/1", "Acme", "acme.io", "Senior SEO Manager", fetch=f)
        self.assertEqual((r["state"], r["company_board"]), ("open", "ashby:acme-inc"))

    def test_board_without_the_role_is_likely_filled(self):
        f = self.fake({"linkedin.com/jobs/view/2": "<html>Apply now</html>",
                       "boards-api.greenhouse.io/v1/boards/acme/jobs": '{"jobs":[{"title":"Account Executive"}]}'})
        r = jobs.open_check("https://www.linkedin.com/jobs/view/2", "Acme", None, "SEO Lead", fetch=f)
        self.assertEqual(r["state"], "likely_filled")

    def test_closed_post_and_login_wall(self):
        f = self.fake({"view/3": "No longer accepting applications", "view/4": "<html>authwall join linkedin</html>"})
        self.assertEqual(jobs.open_check("https://www.linkedin.com/jobs/view/3", "Zed", fetch=f)["state"], "closed")
        self.assertEqual(jobs.open_check("https://www.linkedin.com/jobs/view/4", "Zed", fetch=f)["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
