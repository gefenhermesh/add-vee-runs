#!/usr/bin/env python3
"""The campaign's learning memory: what makes people reply, and what to try next.

Goal (sponsor, 2026-11-19): **raise the reply rate** and find the company profile most likely to want to work
with the sponsor. Every email-1 thread is a record in campaign/learning/outreach_log.jsonl: the features of
the company, the contact and the email, and the outcome. This script turns that log into evidence and into
the next week's mix: mostly what works, plus deliberate exploration so the system keeps learning.

  python campaign/learn.py add <record.json>           log a sent email 1 (features + gmail_thread_id)
  python campaign/learn.py outcome <slug> <class> [--report-requested] [--meeting] [--at ISO]
        class: positive | neutral | negative | auto (out-of-office etc.) | none (settled without reply)
  python campaign/learn.py followup <slug>             count a follow-up sent on that thread
  python campaign/learn.py report                      write campaign/learning/learnings.md and print it
  python campaign/learn.py pick <candidates.json> <n>  choose n companies to audit next (Thompson sampling + exploration)

Statistics, honestly: at a few emails a week, rates are noisy. Every rate is a Beta(1+replies, 1+misses)
posterior with an 80% interval, never a bare percentage, and a feature value with fewer than MIN_N settled
emails is shown as "too early". "pick" samples each candidate's likely reply rate from those posteriors
(Thompson sampling), and reserves EXPLORE_SHARE of the picks for feature values that are still under-tested.
"""
import argparse
import datetime as dt
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "campaign" / "learning" / "outreach_log.jsonl"
REPORT = ROOT / "campaign" / "learning" / "learnings.md"
SETTLE_DAYS = 14          # no reply 14 days after the last touch = settled as no reply
MIN_N = 3                 # below this, a feature value is "too early"
EXPLORE_SHARE = 0.4       # share of each week's picks reserved for under-tested feature values
SAMPLES = 4000

# The features every record carries. Values are short lowercase labels; new values are welcome.
FEATURES = {
    "industry": "security, devtools, data_ai_infra, fintech, hr_tech, martech, vertical_saas, healthcare, home_services, ...",
    "stage": "seed, series_a, series_b, series_c_plus, public",
    "situation": "stealth_exit, early, scaling, established, category_leader",
    "size_band": "1_50, 51_200, 201_1000, 1000_plus",
    "geo": "israel, us, eu, israel_us, ...",
    "marketing_gating": "sweet_spot, single_seo, no_leader_exception",
    "trigger": "funding, launch, marketing_hire, rebrand, competitor_comparison_page, job_post, none",
    "finding_pattern": "absent, losing_to_named_competitors, misrepresented, present_not_recommended, strong",
    "recipient_role": "ceo, cmo_vp_marketing, head_of_growth, pmm, content_seo, other",
    "ask_track": "role, engagement",
    "opener_type": "milestone_congrats, their_words, shared_ground, none",
    "email_variant": "id of the template version, e.g. v4_two_images",
    "subject_style": "how_ai_sees_x, finding_hook, question, other",
    "send_slot": "sun_thu_morning_local, other",
    "contact_verified": "yes, no",
    "buying_journey": "committee, household, considered, transactional (SCOUT.md: who fits)",
    "seo_need": "high, medium, low, unassessed (SCOUT.md: buyer research, competition in search, cost of absence)",
}


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def load():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]


def save(rows):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def settled(r, at):
    o = r.get("outcome") or {}
    if o.get("class") and o["class"] != "auto":
        return True
    last = parse(r.get("last_touch_at") or r.get("sent_at"))
    return bool(last) and (at - last).days >= SETTLE_DAYS


def replied(r, positive_only=False):
    c = (r.get("outcome") or {}).get("class")
    return c == "positive" if positive_only else c in ("positive", "neutral", "negative")


def posterior(k, n, rng):
    draws = sorted(rng.betavariate(1 + k, 1 + n - k) for _ in range(SAMPLES))
    return statistics.fmean(draws), draws[int(0.1 * SAMPLES)], draws[int(0.9 * SAMPLES)]


def stats(rows, at, positive_only=False):
    rng = random.Random(7)
    done = [r for r in rows if settled(r, at)]
    out = {"n_sent": len(rows), "n_settled": len(done)}
    k = sum(replied(r, positive_only) for r in done)
    out["overall"] = (k, len(done), *posterior(k, len(done), rng))
    per = {}
    for f in FEATURES:
        cells = {}
        for r in done:
            v = (r.get("features") or {}).get(f)
            if v is None:
                continue
            c = cells.setdefault(v, [0, 0])
            c[0] += replied(r, positive_only)
            c[1] += 1
        per[f] = {v: (kk, nn, *posterior(kk, nn, rng)) for v, (kk, nn) in cells.items()}
    out["per_feature"] = per
    return out


def cmd_add(a):
    rec = json.loads(Path(a.file).read_text())
    for req in ("slug", "sent_at", "features"):
        if req not in rec:
            sys.exit(f"record needs '{req}'")
    unknown = set(rec["features"]) - set(FEATURES)
    if unknown:
        sys.exit(f"unknown features {sorted(unknown)}; add them to FEATURES first so they're tracked on purpose")
    rows = [r for r in load() if r["slug"] != rec["slug"]]
    rec.setdefault("outcome", {})
    rec.setdefault("followups", 0)
    rows.append(rec)
    save(rows)
    print(f"logged {rec['slug']} ({len(rows)} threads)")


def cmd_outcome(a):
    rows = load()
    for r in rows:
        if r["slug"] == a.slug:
            r["outcome"] = {"class": a.cls, "at": a.at or now().isoformat(timespec="seconds"),
                            "report_requested": a.report_requested, "meeting": a.meeting}
            save(rows)
            print(f"{a.slug}: {a.cls}")
            return
    sys.exit(f"no thread for {a.slug}")


def cmd_followup(a):
    rows = load()
    for r in rows:
        if r["slug"] == a.slug:
            r["followups"] = r.get("followups", 0) + 1
            r["last_touch_at"] = now().isoformat(timespec="seconds")
            save(rows)
            print(f"{a.slug}: follow-up {r['followups']}")
            return
    sys.exit(f"no thread for {a.slug}")


def pct(x):
    return f"{100 * x:.0f}%"


def render(rows, at):
    s_any, s_pos = stats(rows, at), stats(rows, at, positive_only=True)
    k, n, m, lo, hi = s_any["overall"]
    kp, _, mp, lop, hip = s_pos["overall"]
    lines = [f"# What the campaign has learned ({at.date()})", "",
             f"Emails sent: {s_any['n_sent']} · settled: {n} (a reply, or {SETTLE_DAYS} days without one)", "",
             f"**Any reply: {k}/{n}**, likely {pct(m)} (80% range {pct(lo)}–{pct(hi)})  ",
             f"**Positive reply: {kp}/{n}**, likely {pct(mp)} (80% range {pct(lop)}–{pct(hip)})", "",
             "Small numbers: read the ranges, not the point estimates. A value marked *too early* has fewer than "
             f"{MIN_N} settled emails.", ""]
    for f in FEATURES:
        cells = s_any["per_feature"].get(f) or {}
        if not cells:
            continue
        lines.append(f"## {f}")
        lines.append("| value | replies / settled | likely rate | 80% range |")
        lines.append("|---|---|---|---|")
        for v, (kk, nn, mm, l, h) in sorted(cells.items(), key=lambda x: -x[1][2]):
            tag = " *(too early)*" if nn < MIN_N else ""
            lines.append(f"| {v}{tag} | {kk}/{nn} | {pct(mm)} | {pct(l)}–{pct(h)} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def cmd_report(a):
    at = parse(a.at) if a.at else now()
    text = render(load(), at)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text)
    print(text)


def pick(rows, candidates, n, at, seed=None):
    """Choose n candidates: (1-EXPLORE_SHARE) by sampled reply rate, the rest from under-tested values."""
    rng = random.Random(seed)
    s = stats(rows, at)["per_feature"]

    def sampled_rate(c):
        draws = []
        for f, v in (c.get("features") or {}).items():
            kk, nn = (s.get(f, {}).get(v) or (0, 0))[:2]
            draws.append(rng.betavariate(1 + kk, 1 + nn - kk))
        return statistics.fmean(draws) if draws else rng.random()

    def novelty(c):
        return sum(1 for f, v in (c.get("features") or {}).items()
                   if (s.get(f, {}).get(v) or (0, 0))[1] < MIN_N)

    n_explore = round(n * EXPLORE_SHARE)
    pool = list(candidates)
    explore = sorted(pool, key=lambda c: (-novelty(c), rng.random()))[:n_explore]
    explore = [c for c in explore if novelty(c) > 0]
    rest = [c for c in pool if c not in explore]
    exploit = sorted(rest, key=lambda c: -sampled_rate(c))[: n - len(explore)]
    out = [{**c, "why_picked": "exploit"} for c in exploit] + [{**c, "why_picked": "explore"} for c in explore]
    return out


def cmd_pick(a):
    cands = json.loads(Path(a.file).read_text())
    for c in pick(load(), cands, a.n, now()):
        print(f"{c['why_picked']:8s} {c['slug']}  {json.dumps(c.get('features', {}), ensure_ascii=False)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("add"); x.add_argument("file"); x.set_defaults(fn=cmd_add)
    x = sub.add_parser("outcome"); x.add_argument("slug"); x.add_argument("cls", choices=["positive", "neutral", "negative", "auto", "none"])
    x.add_argument("--report-requested", action="store_true"); x.add_argument("--meeting", action="store_true"); x.add_argument("--at")
    x.set_defaults(fn=cmd_outcome)
    x = sub.add_parser("followup"); x.add_argument("slug"); x.set_defaults(fn=cmd_followup)
    x = sub.add_parser("report"); x.add_argument("--at"); x.set_defaults(fn=cmd_report)
    x = sub.add_parser("pick"); x.add_argument("file"); x.add_argument("n", type=int); x.set_defaults(fn=cmd_pick)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
