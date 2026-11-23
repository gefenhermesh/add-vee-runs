#!/usr/bin/env python3
"""A cheap first read of a company's blog for scouting: how developed it is and how well its SEO structure is done.

  python campaign/scout/blog_sample.py <domain> [--prefix /blog/] [--sample 12] [--out file.json]

Free: plain HTTPS only, never Bright Data (SCOUT.md, Bright Data budget). It reads the sitemap (all post URLs and
lastmod dates) and fetches a small, evenly spread sample of posts. It mirrors, in miniature, what add-vee's blog IA
auditor measures on a full run (add-vee docs/pipeline/blog-ia-audit.md):
  - size and life: post count, first/last date, posts in the last 12 months (is the blog developed? add-vee runs its
    blog audit only above 20 posts);
  - topic structure: the main topics, from the words in all post slugs, and how concentrated the blog is;
  - waste / overlap: pairs of posts whose slugs share most of their words (candidate competing intent);
  - internal linking: editorial in-body links from each sampled post to other blog posts (template, nav and
    "related posts" widgets excluded, with add-vee's own rule in html_body.py). add-vee calls a post orphaned in its
    cluster with zero peer links; here "0 links to other posts" is the cheap proxy.
Everything here is a SAMPLE and an INDICATION for choosing companies, never a finding for outreach: only the full
audit's confirmed numbers are quoted to a company. Pages the site refuses are reported as failures, not as empty.
"""
import argparse
import datetime as dt
import gzip
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from html_body import editorial  # noqa: E402  (copied from add-vee: same editorial-link rule)

UA = {"User-Agent": "Mozilla/5.0 (compatible; scout-blog-sample/1.0)"}
NOT_ARTICLES = re.compile(r"^/?(page|category|categories|tag|tags|author|authors|topic|topics|feed|rss|archive|archives|[a-z-]*-?collections?)(/|$)")
PREFIXES = ["/blog/", "/resources/blog/", "/insights/", "/articles/", "/learn/", "/resources/", "/post/", "/posts/", "/news/"]
STOP = set("a an the and or of to for in on with how what why when is are your you vs versus best top guide guides "
           "2019 2020 2021 2022 2023 2024 2025 2026 2027 new tips ways using use do does can it its this that from by "
           "about into our we my why s t".split())
SITEMAP_LIMIT = 25


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data.decode("utf-8", "replace")


def host(u):
    return (urlparse(u).hostname or "").lower().removeprefix("www.")


def sitemap_urls(domain):
    """All <loc> URLs (with lastmod) from robots.txt sitemaps or /sitemap.xml, following sitemap indexes."""
    roots, errors = [], []
    try:
        roots = re.findall(r"(?im)^sitemap:\s*(\S+)", get(f"https://{domain}/robots.txt"))
    except Exception as e:
        errors.append(f"robots.txt: {e}")
    roots = roots or [f"https://{domain}/sitemap.xml", f"https://{domain}/sitemap_index.xml"]
    seen, todo, out = set(), list(roots), {}
    while todo and len(seen) < SITEMAP_LIMIT:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            xml = get(sm)
        except Exception as e:
            errors.append(f"{sm}: {e}")
            continue
        for block in re.findall(r"<(?:url|sitemap)>(.*?)</(?:url|sitemap)>", xml, re.S):
            loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block, re.S)
            if not loc:
                continue
            loc = loc.group(1).replace("&amp;", "&")
            lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
            if "<sitemap>" in xml and re.search(r"\.xml(\.gz)?($|\?)", loc):
                todo.append(loc)
            else:
                out[loc] = (lm.group(1)[:10] if lm else None)
    return out, errors, len(seen)


def articles(urls, domain, prefix=None):
    def is_art(u, p):
        path = urlparse(u).path
        if host(u) != domain.removeprefix("www.") or not path.startswith(p):
            return False
        rest = path[len(p):].strip("/")
        return bool(rest) and not NOT_ARTICLES.match(rest)
    if prefix:
        return prefix, {u: d for u, d in urls.items() if is_art(u, prefix)}
    best = max(PREFIXES, key=lambda p: sum(is_art(u, p) for u in urls))
    return best, {u: d for u, d in urls.items() if is_art(u, best)}


def slug_tokens(u, brand):
    slug = urlparse(u).path.rstrip("/").split("/")[-1]
    return [t for t in re.split(r"[^a-z0-9]+", slug.lower()) if t and t not in STOP and t != brand and not t.isdigit()]


def published(raw):
    m = (re.search(r'article:published_time"\s+content="([0-9-]{10})', raw)
         or re.search(r'"datePublished"\s*:\s*"([0-9-]{10})', raw)
         or re.search(r'<time[^>]+datetime="([0-9-]{10})', raw))
    return m.group(1) if m else None


def sample_evenly(items, n):
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def run(domain, prefix=None, n=12, today=None):
    today = today or dt.date.today()
    domain = domain.lower().removeprefix("https://").removeprefix("http://").strip("/")
    brand = domain.split(".")[0].removeprefix("www")
    urls, errors, n_sitemaps = sitemap_urls(domain)
    prefix, posts = articles(urls, domain, prefix)
    res = {"domain": domain, "date": today.isoformat(), "method": "plain HTTPS, no Bright Data", "sitemaps_read": n_sitemaps,
           "blog_prefix": prefix, "posts_in_sitemap": len(posts), "errors": errors}
    if not posts:
        res["verdict"] = "no blog found in the sitemap (couldn't verify: the blog may live elsewhere or the sitemap was refused)"
        return res

    # topics and overlap from every post slug (free: no page fetches)
    toks = {u: slug_tokens(u, brand) for u in posts}
    df = Counter(t for ts in toks.values() for t in set(ts))
    topics = [(t, c) for t, c in df.most_common(12) if c >= 3]
    covered = sum(1 for ts in toks.values() if any(t in dict(topics[:6]) for t in ts))
    res["top_topics"] = [{"term": t, "posts": c} for t, c in topics]
    res["share_in_top6_topics_pct"] = round(100 * covered / len(posts))
    pairs, items = [], [(u, set(ts)) for u, ts in toks.items() if len(ts) >= 3][:3000]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            jac = len(a & b) / len(a | b)
            if jac >= 0.6:
                pairs.append((round(jac, 2), items[i][0], items[j][0]))
    pairs.sort(reverse=True)
    res["overlap_candidates"] = len(pairs)
    res["overlap_examples"] = [{"similarity": s, "a": a, "b": b} for s, a, b in pairs[:5]]

    # sample posts: newest first by lastmod when present, spread evenly across the whole list
    order = sorted(posts, key=lambda u: posts[u] or "", reverse=True)
    sample, rows = sample_evenly(order, n), []
    post_paths = {urlparse(u).path.rstrip("/") for u in posts}
    for u in sample:
        try:
            raw = get(u)
        except Exception as e:
            rows.append({"url": u, "error": str(e)[:120]})
            continue
        title, text, links = editorial(raw)
        if len(text) < 400:
            rows.append({"url": u, "error": f"body too short ({len(text)} chars): bot check or JS-rendered page"})
            continue
        to_posts = set()
        for h in links:
            t = urljoin(u, h)
            if host(t) == domain.removeprefix("www.") and urlparse(t).path.rstrip("/") in post_paths and urlparse(t).path.rstrip("/") != urlparse(u).path.rstrip("/"):
                to_posts.add(urlparse(t).path.rstrip("/"))
        rows.append({"url": u, "title": title[:120], "published": published(raw), "words": len(text.split()),
                     "_targets": sorted(to_posts)})
    ok = [r for r in rows if "error" not in r]
    # Template guard: a post link that shows up in most sampled posts is a widget (latest posts, a menu the body rule
    # missed), not an author's choice. Found on mybites.io (Elementor): the same ~14 links in every post.
    seen = Counter(x for r in ok for x in r["_targets"])
    template = {x for x, c in seen.items() if len(ok) >= 4 and c >= 0.5 * len(ok)}
    res["template_links_removed"] = len(template)
    for r in ok:
        r["links_to_other_posts"] = len([x for x in r.pop("_targets") if x not in template])
    res["sample"] = rows
    res["sample_fetched"] = len(ok)

    dates = sorted(d for d in [r.get("published") for r in ok] + list(posts.values()) if d)
    if dates:
        res["first_date_seen"], res["last_date_seen"] = dates[0], dates[-1]
    lm_recent = [d for d in posts.values() if d and d >= (today - dt.timedelta(days=365)).isoformat()]
    res["posts_lastmod_last_12m"] = len(lm_recent)
    if ok:
        links = [r["links_to_other_posts"] for r in ok]
        res["avg_links_to_other_posts"] = round(sum(links) / len(links), 1)
        res["share_with_0_links_pct"] = round(100 * sum(1 for x in links if x == 0) / len(links))
        res["median_words"] = sorted(r["words"] for r in ok)[len(ok) // 2]

    # a plain reading of the numbers (indicative only)
    notes = []
    developed = len(posts) > 20
    notes.append(f"{'developed' if developed else 'thin'} blog: {len(posts)} posts under {prefix}"
                 + (" (add-vee's blog audit runs above 20)" if developed else ""))
    if ok:
        z, avg = res["share_with_0_links_pct"], res["avg_links_to_other_posts"]
        notes.append("internal linking looks " + ("weak" if z >= 50 or avg < 1.5 else "partial" if avg < 3 else "decent")
                     + f": {avg} in-body links to other posts on average, {z}% of sampled posts link to none")
    if pairs:
        notes.append(f"{len(pairs)} slug pairs look like overlapping topics (candidate waste)")
    if topics:
        notes.append(f"{res['share_in_top6_topics_pct']}% of posts sit in the 6 main topics "
                     + ("(focused)" if res["share_in_top6_topics_pct"] >= 50 else "(scattered: clusters may be thin)"))
    if len(ok) < len(sample):
        notes.append(f"{len(sample) - len(ok)} of {len(sample)} sampled posts couldn't be read directly (see errors)")
    res["reading"] = notes
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("domain")
    ap.add_argument("--prefix")
    ap.add_argument("--sample", type=int, default=12)
    ap.add_argument("--out")
    a = ap.parse_args()
    res = run(a.domain, a.prefix, a.sample)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k not in ("sample",)}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
