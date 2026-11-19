#!/usr/bin/env python3
"""Scout source readers: turn each source into plain lead records (see campaign/SOURCES.md).

Every reader returns a list of dicts with at least: company, source, source_url, date (if known), and the
signal it carries (funding / marketing_role / open_roles). A lead is not a fact: amounts and dates are
re-checked at a primary source before they are used anywhere (SOURCES.md, "Rules for sources").

Fetching: direct HTTPS first; `brightdata=True` routes through Bright Data's content_crawler unlocker for sites
that block plain fetches (the proxy adds the key). Parsers take raw text so they can be tested offline on the
fixtures in campaign/scout/fixtures/.
"""
import html
import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (research script)"}


def fetch(url, brightdata=False, timeout=40):
    if brightdata:
        body = json.dumps({"zone": "content_crawler", "url": url, "format": "raw"}).encode()
        req = urllib.request.Request("https://api.brightdata.com/request", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"})
    else:
        req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def text_of(page):
    t = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", page)
    t = re.sub(r"<(li|p|h\d|br|div|tr)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t))


AMOUNT = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s*(million|billion|M|B)\b", re.I)
STAGE = re.compile(r"\b(pre-seed|seed|Series [A-H](?:-\d)?|growth|extension)\b", re.I)


def money(s):
    m = AMOUNT.search(s)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1000 if m.group(2).lower() in ("billion", "b") else v


# --- VC Cafe "Weekly Firgun Newsletter" (vccafe.com/feed/) ---------------------------------------------
def firgun_latest_url(feed_xml):
    for title, link in re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", feed_xml, re.S):
        if "Firgun" in title:
            return link.strip()
    return None


def parse_firgun(page, url=""):
    """Lines like 'Kudos <founders> and team <Company> on <...> $50 million ... Series A ...'."""
    date = None
    m = re.search(r"Weekly Firgun Newsletter\s*[–-]\s*([A-Z][a-z]+ \d{1,2},? \d{4})", text_of(page))
    if m:
        date = m.group(1)
    leads = []
    for line in text_of(page).split("\n"):
        m = re.search(r"\b(?:and )?team ([A-Z0-9][\w.&'’ -]{1,40}?)(?: \(([^)]*)\))? on (.+)", line)
        if not m or "$" not in line and "undisclosed" not in line:
            continue
        founders = re.split(r",\s*| and ", line[: m.start()].split(" ", 1)[-1]) if m.start() else []
        founders = [f.strip() for f in founders if re.match(r"^[A-Z][\w'’-]+ [A-Z][\w'’-]+", f.strip())]
        rest = m.group(3)
        leads.append({"company": m.group(1).strip(), "source": "vccafe_firgun", "source_url": url, "date": date,
                      "signal": "funding", "amount_musd": money(rest), "stage": (STAGE.search(rest) or [None])[0],
                      "founders": founders, "note": m.group(2) or "", "raw": line.strip()[:400]})
    return leads


# --- Telegram "hitechjobsmarketing" (t.me/s/hitechjobsmarketing) ----------------------------------------
def parse_telegram_jobs(page, url="https://t.me/s/hitechjobsmarketing"):
    leads = []
    for block, date in re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>.*?<time[^>]*datetime="([^"]+)"',
                                  page, re.S):
        t = html.unescape(re.sub(r"<br\s*/?>", "\n", block))
        t = re.sub(r"<[^>]+>", "", t)
        role = None
        for line in [l.strip(" ‎") for l in t.split("\n") if l.strip(" ‎")]:
            if line.startswith("🔹"):
                role = line.lstrip("🔹 ").strip()
            elif line.startswith("🏢") and role:
                parts = [p.strip() for p in line.lstrip("🏢 ").split("·")]
                leads.append({"company": parts[0], "source": "telegram_hitechjobsmarketing", "source_url": url,
                              "date": date[:10], "signal": "marketing_role", "role": role,
                              "location": next((p.lstrip("📍 ") for p in parts if p.startswith("📍")), None),
                              "years": next((p.lstrip("🧑 ") for p in parts if p.startswith("🧑")), None)})
                role = None
    return leads


# --- Avi Lewis' Hebrew lists ("<Company> גייסו $NM ב<month>, K משרות פתוחות, יושבים ב<place>") -------------
HEB_LINE = re.compile(r"^\s*([^\n]{1,40}?)\s*[\n,]?\s*,?\s*גי[יב]סו\s+(.+)$")


def parse_avi_list(page, url=""):
    t = text_of(page)
    start = t.find("רשימת סטארטאפים")
    end = t.find("פספסתי", start)
    body = t[start:end] if start >= 0 else ""
    # entries are split over lines: "א. \nCompany\n גייסו $NM ..."
    body = re.sub(r"\n\s*([^\n]{1,40})\n\s*(,?\s*גי[יב]סו)", r" \1 \2", body)
    leads = []
    for line in body.split("\n"):
        m = re.match(r"^\s*[א-ת]{1,2}\.\s*(.+?)\s*,?\s*גי[יב]סו\s+(.+)$", line)
        if not m:
            continue
        rest = m.group(2)
        roles = re.search(r"(\d+)\s+משרות", rest) or (re.search(r"משרה פתוחה אחת", rest) and ["", "1"])
        loc = re.search(r"יושבים ב(.+)$", rest)
        leads.append({"company": m.group(1).strip(), "source": "avi_lewis_list", "source_url": url, "signal": "funding",
                      "amount_musd": money(rest), "open_roles": int(roles[1]) if roles else None,
                      "location_he": loc.group(1).strip() if loc else None, "raw": line.strip()[:300]})
    # the page repeats the start of the post in its meta preview: keep the fullest entry per company
    best = {}
    for l in leads:
        score = sum(v is not None for v in l.values())
        if l["company"] not in best or score >= best[l["company"]][0]:
            best[l["company"]] = (score, l)
    return [v for _, v in best.values()]


# --- Job boards (Ashby / Greenhouse / Lever public APIs) -----------------------------------------------
def job_board_urls(board):
    return {"ashby": f"https://api.ashbyhq.com/posting-api/job-board/{board}",
            "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
            "lever": f"https://api.lever.co/v0/postings/{board}?mode=json"}


def parse_job_board(kind, payload):
    d = json.loads(payload)
    if kind == "ashby":
        jobs = [{"title": j.get("title"), "department": j.get("department"), "location": j.get("location"),
                 "url": j.get("jobUrl"), "published": (j.get("publishedAt") or "")[:10]} for j in d.get("jobs", [])]
    elif kind == "greenhouse":
        jobs = [{"title": j.get("title"), "department": None, "location": (j.get("location") or {}).get("name"),
                 "url": j.get("absolute_url"), "published": (j.get("updated_at") or "")[:10]} for j in d.get("jobs", [])]
    else:
        jobs = [{"title": j.get("text"), "department": (j.get("categories") or {}).get("team"),
                 "location": (j.get("categories") or {}).get("location"), "url": j.get("hostedUrl"),
                 "published": None} for j in d]
    mk = re.compile(r"market|growth|content|seo|brand|demand|communications|pr\b|community|gtm", re.I)
    return {"open_roles": len(jobs), "marketing_roles": [j for j in jobs if mk.search(j["title"] or "")],
            "seo_roles": [j for j in jobs if re.search(r"\bseo\b|organic|search", j["title"] or "", re.I)],
            "jobs": jobs}


def read_job_board(board):
    """Try each board type for a company's board name. Returns (kind, parsed) or (None, None)."""
    for kind, url in job_board_urls(board).items():
        try:
            parsed = parse_job_board(kind, fetch(url))
            if parsed["open_roles"]:
                return kind, parsed
        except Exception:
            continue
    return None, None
