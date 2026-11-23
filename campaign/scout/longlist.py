#!/usr/bin/env python3
"""Build the scout's long list from all live sources (SOURCES.md), merged per company.

  python campaign/scout/longlist.py [--avi-url URL ...]     -> campaign/scout/longlist.json (+ a short summary)

Each company record collects every signal found (funding rounds, marketing roles, open-role counts) with its
source, and is marked `known` if it is already in campaign/state.json or was audited before (output/ in add-vee).
`first_seen` is kept between runs, so new arrivals stand out. This step is mechanical: the judgment (quick filter,
recon, gating, features) is the scout session's job (SCOUT.md).
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import readers as R  # noqa: E402

OUT = HERE / "longlist.json"
ALREADY_AUDITED = {"bay", "island", "onyx", "onyx security", "enso"}


def norm(name):
    n = re.sub(r"\(.*?\)", "", name or "").lower()
    n = re.sub(r"\b(security|technologies|technology|inc|ltd|ai|io|labs)\b|[^a-z0-9א-ת ]", " ", n)
    return re.sub(r"\s+", " ", n).strip() or (name or "").lower()


AVI_ACTIVITY = "https://www.linkedin.com/in/avi-lewis/recent-activity/all/"


def collect(avi_urls):
    """Read every source with a reader. Returns (leads, coverage): coverage has one row per source with its lead
    count or its error, so a source that was skipped or failed is visible in the run log, never silent."""
    leads, coverage = [], []

    def run(name, fn):
        try:
            got = fn()
            leads.extend(got)
            coverage.append({"source": name, "leads": len(got), "ok": True})
        except Exception as e:  # report and carry on with the other sources
            coverage.append({"source": name, "leads": 0, "ok": False, "error": str(e)[:200]})

    def firgun():
        url = R.firgun_latest_url(R.fetch("https://www.vccafe.com/feed/"))
        return R.parse_firgun(R.fetch(url), url) if url else []

    run("vccafe_firgun", firgun)
    run("telegram_hitechjobsmarketing", lambda: R.parse_telegram_jobs(R.fetch("https://t.me/s/hitechjobsmarketing")))
    run("nextplay_feed", lambda: R.parse_nextplay_feed(R.fetch("https://nextplayso.substack.com/feed")))
    run("ctech_startups", lambda: R.parse_ctech_startups(R.render("https://www.calcalistech.com/ctechnews/category/5214")))
    run("ctech_appointments", lambda: R.parse_ctech_appointments(R.render("https://www.calcalistech.com/ctechnews/category/31182")))
    for name, feed in R.GENERAL_FEEDS.items():
        run(name, lambda feed=feed, name=name: R.parse_rss_funding(R.fetch(feed), name))
    run("linkedin_list_posters (new posts only, Bright Data; see list_posters.json)", R.list_posters_new_posts)
    for u in avi_urls:
        run(f"avi_lewis {u[:60]}", lambda u=u: R.parse_avi_list(R.fetch(u, brightdata=True), u))
    return leads, coverage


def merge(leads, previous, known):
    today = dt.date.today().isoformat()
    by = {c["key"]: c for c in previous.get("companies", [])}
    for l in leads:
        k = norm(l["company"])
        c = by.setdefault(k, {"key": k, "company": l["company"], "first_seen": today, "signals": []})
        c["last_seen"] = today
        sig = {x: l.get(x) for x in ("signal", "source", "source_url", "date", "amount_musd", "stage", "role",
                                     "location", "open_roles", "founders", "note", "person", "marketing_leader_hire",
                                     "list", "raw") if l.get(x) not in (None, "", [])}
        if sig not in c["signals"]:
            c["signals"].append(sig)
    for c in by.values():
        c["known"] = c["key"] in known
        c["marketing_roles"] = sum(1 for s in c["signals"] if s.get("signal") == "marketing_role")
        c["funding"] = [s for s in c["signals"] if s.get("signal") == "funding"]
        c["marketing_leader_hire"] = any(s.get("marketing_leader_hire") for s in c["signals"])
    return sorted(by.values(), key=lambda c: (c["known"], -len(c["funding"]), -c["marketing_roles"]))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--avi-url", action="append", default=[])
    a = p.parse_args(argv)
    state = json.loads((ROOT / "campaign" / "state.json").read_text())
    known = {norm(x["company"]) for x in state.get("prospects", [])} | {norm(x) for x in ALREADY_AUDITED}
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    leads, coverage = collect(a.avi_url)
    errors = [c for c in coverage if not c["ok"]]
    companies = merge(leads, previous, known)
    OUT.write_text(json.dumps({"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                               "coverage": coverage, "errors": errors, "companies": companies}, indent=1, ensure_ascii=False) + "\n")
    new = [c for c in companies if c["first_seen"] == dt.date.today().isoformat() and not c["known"]]
    print(f"{len(leads)} leads -> {len(companies)} companies ({len(new)} new today)")
    for c in coverage:
        print(f"  source {c['source']}: " + (f"{c['leads']} leads" if c["ok"] else f"FAILED {c.get('error')}"))
    calls, records = R.bd_usage_this_week()
    print(f"  Bright Data datasets this week: {calls} calls, {records} records (caps in campaign/scout/budget.json)")
    for c in companies[:25]:
        f = c["funding"][0] if c["funding"] else {}
        print(f"  {'known ' if c['known'] else '      '}{c['company'][:30]:30s} funding={f.get('amount_musd')} {f.get('stage') or ''} "
              f"mkt_roles={c['marketing_roles']}")


if __name__ == "__main__":
    main()
