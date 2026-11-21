#!/usr/bin/env python3
"""Turn the scout's recon files into proposals and pick the week's set.

  python campaign/scout/propose.py check                 validate every companies/<slug>/scout.json written this run
  python campaign/scout/propose.py add <slug> [<slug>...] add validated companies to state.json as `proposed`
  python campaign/scout/propose.py pick <n>              write campaign/scout/candidates.json from all `proposed`
                                                        companies and choose n with learn.py (exploit + explore)

A recon file must carry everything the decision and the learning loop need: every learn.py FEATURE, the gating
rating, a two-line reason, at least one recipient candidate, and sources with dates (SCOUT.md, honesty rules).
`add` never queues: only the sponsor releases a company (proposed -> queued).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "campaign"))
import learn  # noqa: E402

REQUIRED = ["company", "domain", "reason", "gating_rating", "features", "contacts", "sources"]
SEO_NEED = {"high", "medium", "low"}
GATING = {"sweet_spot", "single_seo", "blocked_seo_team", "no_leader_exception", "too_early", "unclear"}


def problems(rec):
    out = [f"missing {k}" for k in REQUIRED if not rec.get(k)]
    feats = rec.get("features") or {}
    out += [f"feature {f} missing" for f in learn.FEATURES if f not in feats]
    out += [f"unknown feature {f}" for f in feats if f not in learn.FEATURES]
    if rec.get("gating_rating") and rec["gating_rating"] not in GATING:
        out.append(f"gating_rating must be one of {sorted(GATING)}")
    if rec.get("gating_rating") == "blocked_seo_team":
        out.append("blocked by an SEO team: record it, but don't propose it")
    if rec.get("scout_version", 0) >= 3:
        need = rec.get("seo_need") or {}
        if need.get("rating") not in SEO_NEED:
            out.append(f"seo_need.rating must be one of {sorted(SEO_NEED)}")
        elif need["rating"] == "low":
            out.append("low SEO need: record it, but don't propose it")
        else:
            out += [f"seo_need.{k} missing" for k in ("buyer_research", "competitors", "cost_of_absence", "why_not_yet") if not need.get(k)]
        if feats.get("seo_need") != need.get("rating"):
            out.append("feature seo_need must equal seo_need.rating")
    for s in rec.get("sources") or []:
        if not (isinstance(s, dict) and s.get("url") and s.get("date") and s.get("kind") in ("direct", "inferred", "unverified")):
            out.append(f"source needs url, date and kind direct/inferred/unverified: {s}")
            break
    return out


def scout_files():
    return sorted((ROOT / "companies").glob("*/scout.json"))


def cmd_check():
    bad = 0
    for f in scout_files():
        rec = json.loads(f.read_text())
        if rec.get("scout_version", 0) < 2:
            continue  # older hand-made files (e.g. Bay) are not proposals
        p = problems(rec)
        bad += bool(p)
        print(f"{f.parent.name}: {'OK' if not p else '; '.join(p)}")
    return 1 if bad else 0


def cmd_add(slugs):
    state_p = ROOT / "campaign" / "state.json"
    state = json.loads(state_p.read_text())
    have = {p["slug"] for p in state["prospects"]}
    for slug in slugs:
        rec = json.loads((ROOT / "companies" / slug / "scout.json").read_text())
        p = problems(rec)
        if p:
            print(f"{slug}: not added ({'; '.join(p)})")
            continue
        if slug in have:
            print(f"{slug}: already in state.json")
            continue
        state["prospects"].append({"slug": slug, "company": rec["company"], "domain": rec["domain"], "status": "proposed",
                                   "reason": rec["reason"], "gating_rating": rec["gating_rating"],
                                   "features": rec["features"], "source": "scout"})
        print(f"{slug}: proposed")
    state_p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def cmd_pick(n):
    state = json.loads((ROOT / "campaign" / "state.json").read_text())
    cands = [{"slug": p["slug"], "features": p.get("features", {})} for p in state["prospects"] if p.get("status") == "proposed"]
    (HERE / "candidates.json").write_text(json.dumps(cands, indent=1) + "\n")
    picks = learn.pick(learn.load(), cands, n, learn.now())
    for c in picks:
        print(f"{c['why_picked']:8s} {c['slug']}")
    return picks


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "check":
        return cmd_check()
    if argv[1] == "add":
        return cmd_add(argv[2:]) or 0
    if argv[1] == "pick":
        cmd_pick(int(argv[2]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
