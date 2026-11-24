#!/usr/bin/env python3
"""Jobs for the sponsor: remote SEO roles he can apply to from Costa Rica. Part of the daily jobs run (SCOUT.md ->
Daily SEO-jobs route, step 0). Deterministic fetch + screening; the jobs-scout session makes the final call.

Sponsor's request (2026-11-24): every day, the last 24 hours of
  - LinkedIn, "search engine optimization", remote, Latin America;
  - LinkedIn, same, remote, United States: only posts that don't need US work authorization;
  - LinkedIn, same, remote, Europe: only posts that might work with someone in Costa Rica;
  - seojobs.com, last 24 hours, same rules (US posts without work authorization; open to LATAM);
  - no Asia. A daily message with the posts worth applying to and links to apply.

  python campaign/scout/seeker.py fetch            -> campaign/scout/seeker/<date>.json (+ coverage lines)
  python campaign/scout/seeker.py digest <date>    -> campaign/scout/seeker/<date>.md, from the session's verdicts

How a post is screened (`screen()`): the description is read from LinkedIn's public job page (free, no login) and
checked for (a) phrases that require US or EU work authorization or residence, (b) phrases that open the role to
LATAM, the Americas, anywhere, or contractors, (c) Asia locations, (d) junior/intern seniority. The result is a
`lean` (apply / maybe / skip) with the matched sentences quoted, so the session can confirm or overturn it.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "seeker"
SEEN = OUT / "seen.jsonl"
sys.path.insert(0, str(HERE))
import jobs  # noqa: E402  (LinkedIn card parser, paid Web Unlocker fetch with cap + log)
import readers as R  # noqa: E402  (page text)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
QUERY = "search engine optimization"
REGIONS = {"latam": "Latin America", "us": "United States", "europe": "Europe"}
MAX_DETAILS = 200          # 3 searches x 60 cards, before de-duplication

LATAM = r"latin america|latam|south america|central america|costa rica|the americas|americas|north and south america"
POS = re.compile(rf"\b({LATAM}|worldwide|anywhere in the world|work from anywhere|globally remote|remote[- ]first,? global|"
                 r"any (country|location)|independent contractor|as an? contractor|contractor (role|position|basis|agreement)|"
                 r"type of contract: contractor|via deel|remote\.com|(us|u\.s\.|american|est|pst|cst) time ?zones?|"
                 r"overlap with (est|pst|cst|us|north american))\b", re.I)
NEG_US = re.compile(r"\b(authori[sz]ed to work in the (united states|u\.?s\.?a?)|(u\.?s\.?|united states) work authori[sz]ation|"
                    r"(u\.?s\.?|united states) citizen|green card|w-?2\b|eligible to work in the (united states|u\.?s\.?)|"
                    r"security clearance|(not|unable to|cannot|can't|won't) (provide |offer )?(visa )?sponsor|"
                    r"without (the need for )?(visa )?sponsorship|no (visa )?sponsorship|"
                    r"(must|need to|required to) (reside|live|be located|be based) (in|within) the (united states|u\.?s\.?)|"
                    r"(us|u\.s\.)-based( candidates)?( only)?|remote \(u\.?s\.?( only| based)?\)|"
                    r"within the (united states|u\.?s\.?|continental us))\b", re.I)
NEG_EU = re.compile(r"\b((right|eligib\w*|authori[sz]ed|permit) to work in (the )?(uk|eu|european union|europe|eea|[A-Z][a-z]+)|"
                    r"(must|need to|required to) (reside|live|be located|be based) in (the )?(uk|eu|europe|[A-Z][a-z]+)|"
                    r"eu (citizens?|work permit)|based in (the )?(uk|eu|europe) only|(uk|eu|cet|cest|gmt) (hours|time ?zone) only)\b", re.I)
ASIA = re.compile(r"\b(india|philippines|pakistan|bangladesh|vietnam|indonesia|malaysia|singapore|china|hong kong|japan|"
                  r"korea|thailand|sri lanka|nepal|taiwan|cambodia|myanmar|apac|asia)\b", re.I)
# A broad word ("worldwide", "Americas", "anywhere") only counts in a sentence about where the person can work;
# company boilerplate ("customers worldwide", "the world's leading network") doesn't.
WORK_CONTEXT = re.compile(r"\b(remote|candidates?|applicants?|hire|hiring|work(ing)? from|based|reside|located|location|"
                          r"time ?zones?|contract(or)?s?|position|role is open|open to)\b", re.I)
STRONG_LATAM = re.compile(r"\b(latin america|latam|south america|central america|costa rica)\b", re.I)
ONSITE = re.compile(r"\b(in[- ]office|on[- ]?site|onsite|hybrid|in[- ]person|presencial|h[ií]brido)\b", re.I)
JUNIOR = re.compile(r"\b(intern(ship)?|junior|jr\.?|entry[- ]level|trainee|assistant|graduate|practicante|pasante|"
                    r"est[aá]gi\w*|assistente|asistente|auxiliar|aprendiz)\b", re.I)
SEO_ROLE = re.compile(r"\b(seo|geo|aeo|search|organic|b\u00fasqueda|busca org\u00e2nica)\b", re.I)  # the title must be an SEO role


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def search_url(region, window_s=86400):
    return "https://www.linkedin.com/jobs/search?" + urllib.parse.urlencode(
        {"keywords": QUERY, "location": REGIONS[region], "f_TPR": f"r{int(window_s)}", "f_WT": "2"})


def description(page):
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', page, re.S)
    if not m:
        return ""
    t = re.sub(r"<(br|li|p)[^>]*>", "\n", m.group(1))
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def sentences_with(rx, text, n=2):
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n", text):
        if rx.search(s) and s.strip() not in out:
            out.append(s.strip()[:220])
        if len(out) >= n:
            break
    return out


def screen(post, desc):
    """lean: apply / maybe / skip, with reasons and the quoted sentences behind them."""
    where = f"{post.get('location', '')} {post.get('title', '')}"
    text = f"{post.get('title', '')}\n{desc}"
    why, quotes = [], []
    if ASIA.search(where):
        return {"lean": "skip", "why": ["located in Asia"], "quotes": []}
    if JUNIOR.search(post.get("title", "")):
        return {"lean": "skip", "why": ["junior or intern role"], "quotes": []}
    if not SEO_ROLE.search(post.get("title", "")):
        return {"lean": "skip", "why": ["not an SEO role"], "quotes": []}
    onsite = sentences_with(ONSITE, text)
    if onsite and not re.search(r"\b(fully remote|100% remote|remote[- ]first)\b", text, re.I):
        return {"lean": "skip", "why": ["not fully remote (in-office, on-site or hybrid)"], "quotes": onsite}
    neg = NEG_US if post["region"] in ("us", "seojobs") else NEG_EU if post["region"] == "europe" else re.compile(
        NEG_US.pattern + "|" + NEG_EU.pattern, re.I)
    pos_q = [q for q in sentences_with(POS, text, n=6) if STRONG_LATAM.search(q) or WORK_CONTEXT.search(q)][:2]
    neg_q = sentences_with(neg, text)
    if neg_q and not re.search(LATAM, " ".join(neg_q), re.I):
        return {"lean": "skip", "why": ["requires local work authorization or residence"], "quotes": neg_q}
    if pos_q:
        return {"lean": "apply", "why": ["open to LATAM, the Americas, anywhere, or contractors"], "quotes": pos_q}
    if post["region"] == "latam":
        return {"lean": "apply", "why": ["remote, listed for Latin America, no residence limit stated"], "quotes": []}
    if post["region"] in ("us", "seojobs"):
        # sponsor, 2026-11-24: a remote US post that doesn't ask about work authorization, sponsorship, citizenship
        # or US residence is worth applying to; some US companies will hire him as a contractor.
        if not desc:
            return {"lean": "maybe", "why": ["remote; description not read, so work-authorization terms unknown"], "quotes": []}
        return {"lean": "apply", "why": ["remote; no work-authorization, sponsorship or residence requirement stated"], "quotes": []}
    return {"lean": "skip", "why": ["Europe post with nothing suggesting it would hire in Costa Rica"], "quotes": []}


def role_key(p):
    return re.sub(r"\(.*?\)", "", p["title"]).strip().lower() + " @ " + p["company"].lower()


def seen():
    """Job ids and roles (title @ company) seen on earlier days: a role re-posted under new ids isn't new."""
    ids, roles = set(), set()
    if SEEN.exists():
        for l in SEEN.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                ids.add(r["job_id"])
                roles.add(r.get("role", ""))
    return ids, roles


def fetch(now=None, fetcher=get, detail_fetcher=get, paid=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    OUT.mkdir(exist_ok=True)
    known, keyset = seen()
    coverage, posts, all_ids = [], [], []
    for region in REGIONS:
        got, last = None, None
        for attempt in range(3):  # LinkedIn answers 429 to bursts; wait and try again
            try:
                got = jobs.parse(fetcher(search_url(region)), region)
                break
            except Exception as e:
                last = e
                time.sleep(30 * (attempt + 1))
        if got is None:
            coverage.append(f"linkedin_{region}_remote: FAILED ({type(last).__name__}: {last})")
            continue
        coverage.append(f"linkedin_{region}_remote: {len(got)} posts")
        time.sleep(5)
        for p in got:
            all_ids.append((p["job_id"], role_key(p)))
            if p["job_id"] in known or role_key(p) in keyset:  # the same role re-posted for many cities counts once
                continue
            keyset.add(role_key(p))
            posts.append({**p, "region": region})
    try:  # seojobs.com refuses plain requests; it goes through the capped Web Unlocker
        page, err = (paid or jobs.paid_fetch)("https://www.seojobs.com/jobs/")
        got = [] if err else jobs.parse_seojobs(page, max_age_days=1, now=now)
        coverage.append(f"seojobs: {len(got)} posts (last 24 h)" if not err else f"seojobs: FAILED ({err})")
        for p in got:
            p["seojobs_page"] = True
            all_ids.append((p["job_id"], role_key(p)))
            if p["job_id"] not in known and role_key(p) not in keyset:
                keyset.add(role_key(p))
                posts.append({**p, "region": "seojobs"})
    except Exception as e:
        coverage.append(f"seojobs: FAILED ({type(e).__name__}: {str(e)[:120]})")
    for i, p in enumerate(posts):
        desc = ""
        relevant = SEO_ROLE.search(p["title"]) and not JUNIOR.search(p["title"]) and not ASIA.search(p.get("location", ""))
        if p["region"] != "seojobs" and relevant and i < MAX_DETAILS:
            for attempt in range(3):  # LinkedIn rate-limits bursts; back off and retry
                try:
                    desc = description(detail_fetcher(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{p['job_id']}"))
                    p.pop("detail_error", None)
                    break
                except Exception as e:
                    p["detail_error"] = str(e)[:80]
                    time.sleep(5 * (attempt + 1))
            time.sleep(1.5)
        elif p["region"] != "seojobs" and relevant:
            p["detail_error"] = "over the daily detail-page limit"
        if p["region"] == "seojobs" and relevant and p.get("url"):
            try:  # seojobs job pages also refuse plain requests: one capped Web Unlocker request per relevant post
                page, err = (paid or jobs.paid_fetch)(p["url"])
                desc = "" if err else R.text_of(page)[:6000]
            except Exception as e:
                p["detail_error"] = str(e)[:80]
        p["screen"] = screen(p, desc)
        p["apply_url"] = p.get("url")
        p["excerpt"] = desc[:600]
    day = now.date().isoformat()
    path = OUT / f"{day}.json"
    if path.exists():  # a second run the same day adds to that day's list instead of replacing it
        old = json.loads(path.read_text())
        posts_all, coverage_all = old["posts"] + posts, old["coverage"] + coverage
    else:
        posts_all, coverage_all = posts, coverage
    path.write_text(json.dumps({"date": day, "coverage": coverage_all, "posts": posts_all}, indent=1,
                               ensure_ascii=False) + "\n")
    with SEEN.open("a") as f:
        for jid, role in dict(all_ids).items():
            if jid not in known:
                f.write(json.dumps({"job_id": jid, "role": role, "seen_at": now.isoformat(timespec="seconds")}) + "\n")
    return coverage, posts


def digest(day):
    """The daily message, from the session's verdicts in <day>.json (`final`: apply / maybe / skip, `note`)."""
    d = json.loads((OUT / f"{day}.json").read_text())
    rows = {"apply": [], "maybe": []}
    for p in d["posts"]:
        v = p.get("final") or p["screen"]["lean"]
        if v in rows:
            rows[v].append(p)
    lines = [f"SEO jobs for you, {day} (remote, last 24 hours; LinkedIn LATAM, US and Europe, seojobs.com)", ""]
    for v, head in (("apply", "Worth applying"), ("maybe", "Maybe: check the location terms")):
        if rows[v]:
            lines.append(f"{head}:")
            for p in rows[v]:
                note = p.get("note") or "; ".join(p["screen"]["why"])
                lines.append(f"- {p['title']} at {p['company']} ({p['location'] or 'remote'}): {note}. Apply: {p['apply_url']}")
            lines.append("")
    skipped = sum(1 for p in d["posts"] if (p.get("final") or p["screen"]["lean"]) == "skip")
    lines.append(f"Skipped {skipped} (not SEO, junior, Asia, local work authorization, or Europe-only). Sources: "
                 + "; ".join(d["coverage"]))
    md = "\n".join(lines) + "\n"
    (OUT / f"{day}.md").write_text(md)
    return md


def main(argv=None):
    a = argparse.ArgumentParser()
    sub = a.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    g = sub.add_parser("digest")
    g.add_argument("day")
    a = a.parse_args(argv)
    if a.cmd == "fetch":
        coverage, posts = fetch()
        from collections import Counter
        print("\n".join(coverage))
        print(f"{len(posts)} new posts; lean: {dict(Counter(p['screen']['lean'] for p in posts))}")
    else:
        print(digest(a.day))


if __name__ == "__main__":
    main()
