#!/usr/bin/env python3
"""Daily SEO-jobs route, step 1: LinkedIn's public job search -> a stored list of hiring companies. Deterministic.

Sources (sponsor, 2026-11-20; one page each, one Web Unlocker request each, see SOURCES): LinkedIn Jobs US + Europe,
Wellfound's SEO Specialist page, SEOjobs.com's newest, VC portfolio boards on Getro (Accel, General Catalyst: every
company is VC-backed and carries its stage), and Berlin Startup Jobs' SEO skill page.

Only what changed is handled: each source's page-1 job ids are remembered in jobs_sources.json. A page whose ids are
the same as last time is reported "unchanged" and skipped; otherwise only posts never seen before are stored, and
only companies never seen before are printed for classification. Pages beyond the first are never read; if every
post on a page is new (the page may have overflowed since the last run), the coverage line says so.

Sponsor request (2026-11-20): every 24 hours, read LinkedIn Jobs for "search engine optimization" posted in the
last 24 hours, in the United States and in Europe (one results page each: LinkedIn's location filter is coarse),
keep every company in a stored list so new ones are cheap to spot, and send the startups among them through the
regular scout route with the "I'd love to be considered" outreach track (SCOUT.md -> Daily SEO-jobs route).

This is the public, logged-out search page read through Bright Data's Web Unlocker (`content_crawler` zone): two
requests a day, not the LinkedIn dataset scrapers, and no company or person page is opened.

  python campaign/scout/jobs.py fetch [--only a,b]   read page 1 of every source, keep only what changed, print the NEW companies
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
SOURCE_STATE = HERE / "jobs_sources.json"
COMPANIES = HERE / "jobs_companies.json"
API = "https://api.brightdata.com/request"
QUERY = "search engine optimization"
REGIONS = {"us": "United States", "europe": "Europe"}
CLASSES = {"startup", "agency", "recruiter", "enterprise", "other", "unknown"}
LATE_STAGES = {"ipo", "acquisition", "acquired", "private_equity", "public"}
SEO_TITLE = re.compile(r"\b(seo|geo|aeo|search|organic)\b", re.I)
WF_SIZE = {"SIZE_1_10": "1-10", "SIZE_11_50": "11-50", "SIZE_51_200": "51-200", "SIZE_201_500": "201-500",
           "SIZE_501_1000": "501-1000", "SIZE_1001_5000": "1001-5000", "SIZE_5001_10000": "5001-10000"}

CARD = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"(.*?)(?=data-entity-urn="urn:li:jobPosting:|\Z)', re.S)


def search_url(region):
    q = urllib.request.quote(QUERY)
    loc = urllib.request.quote(REGIONS[region])
    return f"https://www.linkedin.com/jobs/search?keywords={q}&location={loc}&f_TPR=r86400"


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def norm_name(name):
    n = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    n = re.sub(r"\b(inc|llc|ltd|limited|gmbh|ag|bv|sa|sas|corp|co|the)\b", " ", n)
    return re.sub(r"\s+", "-", n.strip())


def company_key(url, name):
    m = re.search(r"linkedin\.com/company/([^/?#\"]+)", url or "")
    return m.group(1).lower() if m else "name:" + norm_name(name)


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


def parse_wellfound(page, max_age_days=21, now=None):
    """Wellfound role page: its embedded data has each startup's size and each listing's start date."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))["props"]["pageProps"].get("apolloState", {}).get("data", {})
    now = now or dt.datetime.now(dt.timezone.utc)
    posts = []
    for key, st in data.items():
        if not key.startswith("StartupResult:"):
            continue
        for ref in st.get("highlightedJobListings") or []:
            job = data.get(ref.get("__ref"), {})
            if not job or not SEO_TITLE.search(job.get("title", "")):
                continue
            start = dt.datetime.fromtimestamp(job.get("liveStartAt") or 0, dt.timezone.utc)
            if (now - start).days > max_age_days:
                continue
            posts.append({"job_id": f"wf-{job['id']}", "title": job["title"], "company": st["name"],
                          "company_url": f"https://wellfound.com/company/{st['slug']}",
                          "company_key": "name:" + norm_name(st["name"]),
                          "location": ", ".join(job.get("locationNames") or []) or None,
                          "posted": start.date().isoformat(),
                          "url": f"https://wellfound.com/jobs/{job['id']}-{job.get('slug', '')}",
                          "region": "wellfound", "size": WF_SIZE.get(st.get("companySize"), st.get("companySize")),
                          "about": st.get("highConcept")})
    return posts


def parse_seojobs(page, max_age_days=3, now=None):
    """SEOjobs.com newest listings; only the last few days (the stored list drops repeats anyway)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    posts = []
    for item in page.split('<div class="job-item">')[1:]:
        a = re.search(r'<h3><a href="([^"]+)"[^>]*>(.*?)</a>', item, re.S)
        comp = re.search(r'class="job-company">(.*?)</div>', item, re.S)
        loc = re.search(r'class="job-location-detail"[^>]*>(.*?)</div>', item, re.S)
        when = re.search(r'class="job-date">(.*?)</div>', item, re.S)
        if not (a and comp):
            continue
        try:
            posted = dt.datetime.strptime(text(when.group(1)), "%B %d, %Y").date() if when else None
        except ValueError:
            posted = None
        if posted and (now.date() - posted).days > max_age_days:
            continue
        slug = a.group(1).rstrip("/").rsplit("/", 1)[-1]
        name = text(comp.group(1)).split("|")[0].strip()  # the salary follows a "|" in the same element
        posts.append({"job_id": f"sj-{slug}", "title": text(a.group(2)), "company": name, "company_url": None,
                      "company_key": "name:" + norm_name(name), "location": text(loc.group(1)) if loc else None,
                      "posted": posted.isoformat() if posted else None, "url": a.group(1), "region": "seojobs"})
    return posts


def parse_getro(page, max_age_days=10, now=None, board=None):
    """A VC portfolio job board on Getro (newest first). Drops companies past the startup stage (IPO, acquired, PE)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    found = json.loads(m.group(1))["props"]["pageProps"]["initialState"]["jobs"]["found"]
    now = now or dt.datetime.now(dt.timezone.utc)
    posts = []
    for j in found:
        org = j.get("organization") or {}
        created = dt.datetime.fromtimestamp(j.get("createdAt") or 0, dt.timezone.utc)
        if not SEO_TITLE.search(j.get("title", "")) or (now - created).days > max_age_days:
            continue
        if (org.get("stage") or "") in LATE_STAGES:
            continue
        posts.append({"job_id": f"getro-{j['id']}", "title": j["title"], "company": org.get("name", ""),
                      "company_url": None, "company_key": "name:" + norm_name(org.get("name")),
                      "location": ", ".join(j.get("locations") or []) or None, "posted": created.date().isoformat(),
                      "url": j.get("url"), "region": board or "getro", "stage": org.get("stage")})
    return posts


def parse_berlin(page, now=None):
    """Berlin Startup Jobs, SEO skill page (startups only, a handful of posts)."""
    posts = []
    for item in page.split('<li class="bjs-jlid">')[1:]:
        a = re.search(r'bjs-jlid__h"><a href="([^"]+)">(.*?)</a>', item, re.S)
        comp = re.search(r'class="bjs-jlid__b"[^>]*>(.*?)</a>', item, re.S)
        if not (a and comp):
            continue
        slug = a.group(1).rstrip("/").rsplit("/", 1)[-1]
        name = text(comp.group(1))
        posts.append({"job_id": f"bsj-{slug}", "title": text(a.group(2)), "company": name, "company_url": None,
                      "company_key": "name:" + norm_name(name), "location": "Berlin", "posted": None,
                      "url": a.group(1), "region": "berlinstartupjobs"})
    return posts


def parse_linkedin(region):
    return lambda page, now=None: parse(page, region)


SOURCES = {
    "linkedin_us": (search_url("us"), parse_linkedin("us")),
    "linkedin_europe": (search_url("europe"), parse_linkedin("europe")),
    "wellfound": ("https://wellfound.com/role/seo-specialist", parse_wellfound),
    "seojobs": ("https://www.seojobs.com/jobs/", parse_seojobs),
    "getro_accel": ("https://jobs.accel.com/jobs?q=seo", lambda pg, now=None: parse_getro(pg, now=now, board="accel")),
    "getro_general_catalyst": ("https://jobs.generalcatalyst.com/jobs?q=seo",
                               lambda pg, now=None: parse_getro(pg, now=now, board="general_catalyst")),
    "berlinstartupjobs": ("https://berlinstartupjobs.com/skill-areas/seo/", parse_berlin),
}


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
            if c is None:  # the same company may already be stored under another source's key
                alias = next((k for k, v in companies.items() if norm_name(v["name"]) == norm_name(p["company"])), None)
                if alias:
                    p = {**p, "company_key": alias}
                    c = companies[alias]
            if c is None:
                c = companies[p["company_key"]] = {"name": p["company"], "company_url": p["company_url"],
                                                   "first_seen": today, "posts": [], "class": None}
                new_companies.append(p["company_key"])
            c["last_seen"] = today
            c["posts"].append({"job_id": p["job_id"], "title": p["title"], "location": p["location"],
                               "posted": p["posted"], "url": p["url"], "region": p["region"]})
            for extra in ("size", "about", "stage"):
                if p.get(extra):
                    c[extra] = p[extra]
    COMPANIES.write_text(json.dumps(companies, indent=1, ensure_ascii=False) + "\n")
    return [{"key": k, "name": companies[k]["name"], "company_url": companies[k]["company_url"],
             "titles": sorted({x["title"] for x in companies[k]["posts"]}),
             "locations": sorted({x["location"] or "" for x in companies[k]["posts"]}),
             "sources": sorted({x["region"] for x in companies[k]["posts"]}),
             **{e: companies[k][e] for e in ("size", "about", "stage") if companies[k].get(e)}} for k in new_companies]


def known_job_ids():
    if not SEEN.exists():
        return set()
    return {json.loads(l)["job_id"] for l in SEEN.read_text().splitlines() if l.strip()}


def run_sources(fetch, now, only=None):
    """Read page 1 of each source; handle only what changed since the last run. Returns (coverage, posts)."""
    state = json.loads(SOURCE_STATE.read_text()) if SOURCE_STATE.exists() else {}
    known = known_job_ids()
    coverage, posts = [], []
    for name, (url, parser) in SOURCES.items():
        if only and name not in only:
            continue
        try:
            page, err = fetch(url)
        except Exception as e:  # report, never hide
            coverage.append(f"{name}: FAILED ({type(e).__name__}: {e})")
            continue
        got = parser(page, now=now)
        ids = sorted(p["job_id"] for p in got)
        prev = state.get(name, {})
        if not page.strip() or err:
            coverage.append(f"{name}: FAILED ({err or 'empty page'})")
            continue
        if ids and ids == prev.get("ids"):
            coverage.append(f"{name}: unchanged since {prev.get('run', '?')[:16]}, skipped")
            state[name] = {**prev, "checked": now.isoformat(timespec="seconds")}
            continue
        new = [p for p in got if p["job_id"] not in known]
        line = f"{name}: {len(got)} relevant posts, {len(new)} new"
        if got and len(new) == len(got) and prev.get("ids"):
            line += " (every post on the page is new: some older ones may have been missed)"
        coverage.append(line)
        posts += new
        state[name] = {"run": now.isoformat(timespec="seconds"), "ids": ids}
    SOURCE_STATE.write_text(json.dumps(state, indent=1) + "\n")
    return coverage, posts


def cmd_fetch(a):
    now = dt.datetime.now(dt.timezone.utc)
    coverage, posts = run_sources(fetch_page, now, only=a.only.split(",") if a.only else None)
    new = store(posts, now)
    print(json.dumps({"coverage": coverage, "new_posts": len(posts), "new_companies": new}, indent=1, ensure_ascii=False))


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
    x = sub.add_parser("fetch"); x.add_argument("--only", help="comma-separated source names"); x.set_defaults(fn=cmd_fetch)
    x = sub.add_parser("parse"); x.add_argument("html"); x.set_defaults(fn=cmd_parse)
    x = sub.add_parser("classify"); x.add_argument("file"); x.set_defaults(fn=cmd_classify)
    x = sub.add_parser("startups"); x.add_argument("--date"); x.set_defaults(fn=cmd_startups)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
