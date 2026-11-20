#!/usr/bin/env python3
"""Daily SEO-jobs route, step 1: LinkedIn's public job search -> a stored list of hiring companies. Deterministic.

Sponsor request (2026-11-20): every 24 hours, read LinkedIn Jobs for "search engine optimization" posted in the
last 24 hours, in the United States and in Europe (one results page each: LinkedIn's location filter is coarse),
keep every company in a stored list so new ones are cheap to spot, and send the startups among them through the
regular scout route with the "I'd love to be considered" outreach track (SCOUT.md -> Daily SEO-jobs route).

This is the public, logged-out search page read through Bright Data's Web Unlocker (`content_crawler` zone): two
requests a day, not the LinkedIn dataset scrapers, and no company or person page is opened.

  python campaign/scout/jobs.py fetch            fetch both pages, store every post, print the NEW companies (JSON)
  python campaign/scout/jobs.py parse <html>     parse a saved page (tests, debugging)
  python campaign/scout/jobs.py classify <json>  record the session's cheap classification of new companies
  python campaign/scout/jobs.py startups [--date YYYY-MM-DD]   the companies classified "startup" on that day

Files:
  campaign/scout/jobs_seen.jsonl     every post ever seen: {job_id, title, company, company_url, location, posted, url, region, seen_at}
  campaign/scout/jobs_companies.json one row per company (keyed by LinkedIn company slug): first_seen, last_seen, posts,
                                     class (startup | agency | recruiter | enterprise | other | unknown), why, classified_at
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEN = HERE / "jobs_seen.jsonl"
COMPANIES = HERE / "jobs_companies.json"
API = "https://api.brightdata.com/request"
QUERY = "search engine optimization"
REGIONS = {"us": "United States", "europe": "Europe"}
CLASSES = {"startup", "agency", "recruiter", "enterprise", "other", "unknown"}

CARD = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"(.*?)(?=data-entity-urn="urn:li:jobPosting:|\Z)', re.S)


def search_url(region):
    q = urllib.request.quote(QUERY)
    loc = urllib.request.quote(REGIONS[region])
    return f"https://www.linkedin.com/jobs/search?keywords={q}&location={loc}&f_TPR=r86400"


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def company_key(url, name):
    m = re.search(r"linkedin\.com/company/([^/?#\"]+)", url or "")
    return m.group(1).lower() if m else "name:" + re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def parse(page, region=None):
    posts = []
    for job_id, body in CARD.findall(page):
        title = re.search(r'base-search-card__title">(.*?)</h3>', body, re.S)
        sub = re.search(r'base-search-card__subtitle">(.*?)</h4>', body, re.S)
        curl = re.search(r'href="(https://[^"]*linkedin\.com/company/[^"?]+)', sub.group(1)) if sub else None
        loc = re.search(r'job-search-card__location">(.*?)</span>', body, re.S)
        when = re.search(r'<time[^>]*datetime="([^"]+)"', body)
        link = re.search(r'base-card__full-link[^>]*href="([^"?]+)', body)
        name = text(sub.group(1)) if sub else ""
        if not (title and name):
            continue
        posts.append({"job_id": job_id, "title": text(title.group(1)), "company": name,
                      "company_url": curl.group(1) if curl else None, "company_key": company_key(curl and curl.group(1), name),
                      "location": text(loc.group(1)) if loc else None, "posted": when.group(1) if when else None,
                      "url": link.group(1) if link else f"https://www.linkedin.com/jobs/view/{job_id}", "region": region})
    return posts


def fetch_page(url):
    body = json.dumps({"zone": "content_crawler", "url": url, "format": "raw"}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json",
                                                           "Authorization": "Bearer placeholder"})  # proxy injects the key
    with urllib.request.urlopen(req, timeout=150) as r:
        err = r.headers.get("x-brd-error-code")
        page = r.read().decode("utf-8", "ignore")
    return page, err


def load_companies():
    return json.loads(COMPANIES.read_text()) if COMPANIES.exists() else {}


def store(posts, now, companies=None):
    """Append unseen posts; update the company list. Returns the companies seen for the first time."""
    companies = load_companies() if companies is None else companies
    seen_ids = set()
    if SEEN.exists():
        seen_ids = {json.loads(l)["job_id"] for l in SEEN.read_text().splitlines() if l.strip()}
    new_companies, today = [], now.date().isoformat()
    with SEEN.open("a") as f:
        for p in posts:
            if p["job_id"] in seen_ids:
                continue
            seen_ids.add(p["job_id"])
            f.write(json.dumps({**p, "seen_at": now.isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
            c = companies.get(p["company_key"])
            if c is None:
                c = companies[p["company_key"]] = {"name": p["company"], "company_url": p["company_url"],
                                                   "first_seen": today, "posts": [], "class": None}
                new_companies.append(p["company_key"])
            c["last_seen"] = today
            c["posts"].append({"job_id": p["job_id"], "title": p["title"], "location": p["location"],
                               "posted": p["posted"], "url": p["url"], "region": p["region"]})
    COMPANIES.write_text(json.dumps(companies, indent=1, ensure_ascii=False) + "\n")
    return [{"key": k, "name": companies[k]["name"], "company_url": companies[k]["company_url"],
             "titles": sorted({x["title"] for x in companies[k]["posts"]}),
             "locations": sorted({x["location"] or "" for x in companies[k]["posts"]})} for k in new_companies]


def cmd_fetch(a):
    now = dt.datetime.now(dt.timezone.utc)
    posts, coverage = [], []
    for region in REGIONS:
        url = search_url(region)
        try:
            page, err = fetch_page(url)
            got = parse(page, region)
            coverage.append(f"{region}: {len(got)} posts" + (f" (Bright Data {err})" if err else ""))
            if not got:
                coverage[-1] += " FAILED: no job cards parsed"
            posts += got
        except Exception as e:  # report, never hide
            coverage.append(f"{region}: FAILED ({type(e).__name__}: {e})")
    new = store(posts, now)
    print(json.dumps({"coverage": coverage, "posts": len(posts), "new_companies": new}, indent=1, ensure_ascii=False))


def cmd_parse(a):
    print(json.dumps(parse(Path(a.html).read_text(errors="ignore")), indent=1, ensure_ascii=False))


def cmd_classify(a):
    rows = json.loads(Path(a.file).read_text())
    companies = load_companies()
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    for r in rows:
        if r["key"] not in companies:
            sys.exit(f"unknown company key {r['key']}")
        if r["class"] not in CLASSES:
            sys.exit(f"class must be one of {sorted(CLASSES)}")
        if not r.get("why"):
            sys.exit(f"{r['key']}: a one-line why is required")
        companies[r["key"]].update({"class": r["class"], "why": r["why"], "classified_at": today})
    COMPANIES.write_text(json.dumps(companies, indent=1, ensure_ascii=False) + "\n")
    print(f"classified {len(rows)}")


def cmd_startups(a):
    day = a.date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    out = [{"key": k, **v} for k, v in load_companies().items() if v.get("class") == "startup" and v.get("first_seen") == day]
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    x = sub.add_parser("parse"); x.add_argument("html"); x.set_defaults(fn=cmd_parse)
    x = sub.add_parser("classify"); x.add_argument("file"); x.set_defaults(fn=cmd_classify)
    x = sub.add_parser("startups"); x.add_argument("--date"); x.set_defaults(fn=cmd_startups)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
