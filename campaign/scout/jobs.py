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

Cost (sponsor, 2026-11-20: "overtime just get what changed so the expenses go very low"): every page is read
directly first, for free; Bright Data's Web Unlocker (`content_crawler` zone) is a fallback only when a site refuses
(SEOjobs did), capped per week in budget.json (`unlocker_requests_per_week`) and logged in bd_usage.jsonl. LinkedIn is
read daily; a quiet source is checked less often (interval doubles per unchanged check, up to 4 days, back to daily on
a change). If a LinkedIn day is missed, the next read widens its time window, so nothing is lost. Never the LinkedIn
dataset scrapers; no company or person page is opened.

  python campaign/scout/jobs.py fetch [--only a,b]   read page 1 of every source, keep only what changed, print the NEW companies
  python campaign/scout/jobs.py parse <html>     parse a saved page (tests, debugging)
  python campaign/scout/jobs.py classify <json>  record the session's cheap classification of new companies
  python campaign/scout/jobs.py startups [--date YYYY-MM-DD]   the companies classified "startup" on that day
  python campaign/scout/jobs.py backlog [--limit N]   older-post companies still to classify (catch-up mode until 0)
  python campaign/scout/jobs.py check-open <job url>  free check that a job post is still open

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
FRESH_DAYS = 3  # posts this new are triaged the day they appear; older ones go to the backlog (worked through, not ignored)
BACKLOG_PER_DAY = 40  # backlog companies classified per daily run, until the backlog is cleared
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


def search_url(region, window_s=86400):
    """LinkedIn's public search, posts from the last `window_s` seconds (one day by default; wider after a missed
    day, so a skipped run loses nothing)."""
    q = urllib.request.quote(QUERY)
    loc = urllib.request.quote(REGIONS[region])
    return f"https://www.linkedin.com/jobs/search?keywords={q}&location={loc}&f_TPR=r{int(window_s)}"


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
    """Paid: one Web Unlocker request. Use only through paid_fetch (cap + usage log)."""
    body = json.dumps({"zone": "content_crawler", "url": url, "format": "raw"}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json",
                                                           "Authorization": "Bearer placeholder"})  # proxy injects the key
    with urllib.request.urlopen(req, timeout=150) as r:
        err = r.headers.get("x-brd-error-code")
        page = r.read().decode("utf-8", "ignore")
    return page, err


def paid_fetch(url):
    """A Web Unlocker request, refused past the weekly cap and logged in bd_usage.jsonl (kind "unlocker")."""
    sys.path.insert(0, str(HERE))
    import readers as R
    R.unlocker_check(f"jobs route {url[:80]}")
    R.log_unlocker("jobs route", url)
    return fetch_page(url)


def direct_fetch(url):
    """Free: a plain request with no Bright Data. Most job sites answer it (all but SEOjobs on 2026-11-20)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)",
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "ignore")


def load_companies():
    return json.loads(COMPANIES.read_text()) if COMPANIES.exists() else {}


def is_fresh(p, now):
    """A post worth acting on now: posted within FRESH_DAYS. A post with no date counts as fresh only when its
    source was read before (so it really appeared since the last run), never on a source's first read."""
    if p.get("posted"):
        try:
            return (now.date() - dt.date.fromisoformat(p["posted"][:10])).days <= FRESH_DAYS
        except ValueError:
            return False
    return not p.get("baseline")


def store(posts, now, companies=None):
    """Append unseen posts; update the company list. Returns the companies to triage today: new companies with a
    fresh post, and already-recorded but never-classified companies that just posted a fresh role. Companies whose
    new posts are all older are recorded (so they're never re-read) but not returned: that's how no backlog builds."""
    companies = load_companies() if companies is None else companies
    seen_ids = set()
    if SEEN.exists():
        seen_ids = {json.loads(l)["job_id"] for l in SEEN.read_text().splitlines() if l.strip()}
    new_companies, today, fresh_keys = [], now.date().isoformat(), set()
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
            fresh = is_fresh(p, now)
            c["posts"].append({"job_id": p["job_id"], "title": p["title"], "location": p["location"],
                               "posted": p["posted"], "url": p["url"], "region": p["region"], "fresh": fresh})
            if fresh and not c.get("offered") and c.get("class") in (None, "startup") and not c.get("proposed"):
                fresh_keys.add(p["company_key"])
            elif not fresh and c.get("class") is None and not c.get("offered"):
                c["backlog"] = True  # older post, maybe still open: classified later from the backlog, never dropped
            for extra in ("size", "about", "stage"):
                if p.get(extra):
                    c[extra] = p[extra]
    COMPANIES.write_text(json.dumps(companies, indent=1, ensure_ascii=False) + "\n")
    store.recorded_only = len([k for k in new_companies if k not in fresh_keys])
    triage = [k for k in dict.fromkeys(new_companies + sorted(fresh_keys)) if k in fresh_keys]
    for k in triage:
        companies[k]["offered"] = today  # handed to the session for triage once; never again
    COMPANIES.write_text(json.dumps(companies, indent=1, ensure_ascii=False) + "\n")
    return [{"key": k, "name": companies[k]["name"], "company_url": companies[k]["company_url"],
             "fresh_posts": [{"title": x["title"], "posted": x["posted"], "url": x["url"], "location": x["location"]}
                             for x in companies[k]["posts"] if x.get("fresh")],
             "titles": sorted({x["title"] for x in companies[k]["posts"]}),
             "locations": sorted({x["location"] or "" for x in companies[k]["posts"]}),
             "sources": sorted({x["region"] for x in companies[k]["posts"]}),
             **{e: companies[k][e] for e in ("size", "about", "stage") if companies[k].get(e)}} for k in triage]


def known_job_ids():
    if not SEEN.exists():
        return set()
    return {json.loads(l)["job_id"] for l in SEEN.read_text().splitlines() if l.strip()}


DAILY = {"linkedin_us", "linkedin_europe"}   # LinkedIn's 24-hour search changes every day: always read
MAX_INTERVAL_DAYS = 4                         # a quiet source is checked at least this often


def due(prev, name, now):
    """A source is due once its interval has passed (two hours' slack, so a daily run that drifts still reads it).
    Quiet sources back off: each unchanged check doubles the interval, up to MAX_INTERVAL_DAYS; a change resets it."""
    if name in DAILY or not prev.get("checked"):
        return True
    last = dt.datetime.fromisoformat(prev["checked"])
    return now - last >= dt.timedelta(days=prev.get("interval_days", 1)) - dt.timedelta(hours=2)


def source_url(name, url, prev, now):
    if name.startswith("linkedin_") and prev.get("checked"):
        gap = (now - dt.datetime.fromisoformat(prev["checked"])).total_seconds() + 3600
        return search_url(name.split("_", 1)[1], min(max(gap, 86400), 7 * 86400))
    return url


def run_sources(fetch, now, only=None, direct=None):
    """Read page 1 of each source that is due; handle only what changed since the last run.
    `direct` (free) is tried first when given; `fetch` (paid Web Unlocker) only when the direct read fails or comes
    back with no posts where there were posts before. Returns (coverage, posts)."""
    state = json.loads(SOURCE_STATE.read_text()) if SOURCE_STATE.exists() else {}
    known = known_job_ids()
    coverage, posts = [], []
    for name, (url, parser) in SOURCES.items():
        if only and name not in only:
            continue
        prev = state.get(name, {})
        if not only and not due(prev, name, now):
            coverage.append(f"{name}: quiet, next check after {prev.get('interval_days', 1)} days, skipped (free)")
            continue
        url = source_url(name, url, prev, now)
        page = err = got = None
        how = "direct"
        if direct:
            try:
                page = direct(url)
                got = parser(page, now=now)
                if not got and prev.get("ids"):
                    page = None  # an empty page where there were posts: likely a block page, not a quiet day
            except Exception:
                page = None
        if page is None:
            how = "unlocker"
            try:
                page, err = fetch(url)
            except Exception as e:  # report, never hide
                coverage.append(f"{name}: FAILED ({type(e).__name__}: {e})")
                continue
            if not page.strip() or err:
                coverage.append(f"{name}: FAILED ({err or 'empty page'})")
                continue
            got = parser(page, now=now)
        ids = sorted(p["job_id"] for p in got)
        stamp = now.isoformat(timespec="seconds")
        if ids and ids == prev.get("ids"):
            interval = min(prev.get("interval_days", 1) * 2, MAX_INTERVAL_DAYS)
            coverage.append(f"{name}: unchanged since {prev.get('run', '?')[:16]} ({how}); next check in {interval} days")
            state[name] = {**prev, "checked": stamp, "interval_days": interval, "via": how}
            continue
        new = [{**p, "baseline": not prev.get("ids")} for p in got if p["job_id"] not in known]
        line = f"{name}: {len(got)} relevant posts, {len(new)} new ({how})"
        if got and len(new) == len(got) and prev.get("ids"):
            line += " (every post on the page is new: some older ones may have been missed)"
        coverage.append(line)
        posts += new
        state[name] = {"run": stamp, "checked": stamp, "ids": ids, "interval_days": 1, "via": how}
    SOURCE_STATE.write_text(json.dumps(state, indent=1) + "\n")
    return coverage, posts


def cmd_fetch(a):
    now = dt.datetime.now(dt.timezone.utc)
    coverage, posts = run_sources(paid_fetch, now, only=a.only.split(",") if a.only else None, direct=direct_fetch)
    new = store(posts, now)
    sys.path.insert(0, str(HERE))
    import readers as R
    paid, _ = R.bd_usage_this_week("unlocker")
    print(json.dumps({"coverage": coverage, "new_posts": len(posts), "new_companies": new,
                      "recorded_not_triaged": getattr(store, "recorded_only", 0),
                      "paid_unlocker_requests_this_week": paid}, indent=1, ensure_ascii=False))


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


def backlog_rows(companies):
    """Unclassified companies recorded from older posts, newest post first (likeliest to still be open)."""
    rows = [(k, v) for k, v in companies.items()
            if v.get("backlog") and v.get("class") is None and not v.get("offered")]  # offered = triaged as fresh
    newest = lambda v: max((x.get("posted") or "") for x in v["posts"]) if v["posts"] else ""
    return sorted(rows, key=lambda kv: newest(kv[1]), reverse=True)


def cmd_backlog(a):
    """Today's share of the backlog to classify, and whether the route is still catching up."""
    companies = load_companies()
    rows = backlog_rows(companies)
    take = rows[: a.limit]
    out = [{"key": k, "name": v["name"], "company_url": v.get("company_url"),
            "posts": [{"title": x["title"], "posted": x.get("posted"), "url": x["url"], "location": x.get("location")}
                      for x in v["posts"]],
            **{e: v[e] for e in ("size", "about", "stage") if v.get(e)}} for k, v in take]
    print(json.dumps({"mode": "catching_up" if rows else "routine", "backlog_left": len(rows),
                      "today": out}, indent=1, ensure_ascii=False))


CLOSED_MARKERS = ("no longer accepting applications", "this job is no longer available", "job has expired",
                  "position has been filled", "this job has been closed", "job not found")


def cmd_check_open(a):
    """Is a job post still open? Free direct read; a 404/410 or a 'no longer accepting' notice means closed."""
    import urllib.error
    try:
        page = direct_fetch(a.url).lower()
        state = "closed" if any(m in page for m in CLOSED_MARKERS) else "open"
    except urllib.error.HTTPError as e:
        state = "closed" if e.code in (404, 410) else f"unknown (HTTP {e.code})"
    except Exception as e:
        state = f"unknown ({type(e).__name__})"
    print(json.dumps({"url": a.url, "state": state, "checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}))


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
    x = sub.add_parser("backlog"); x.add_argument("--limit", type=int, default=BACKLOG_PER_DAY); x.set_defaults(fn=cmd_backlog)
    x = sub.add_parser("check-open"); x.add_argument("url"); x.set_defaults(fn=cmd_check_open)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
