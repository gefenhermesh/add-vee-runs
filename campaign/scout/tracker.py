#!/usr/bin/env python3
"""The sponsor's apply tracker (sponsor, 2026-11-25): https://claude.ai/artifact/7idQXkKrxYLBpAkVBSdFhj

A published page with a `db` collection `jobs`, one document per role; he ticks "applied" there. The daily jobs scout
adds each day's roles worth applying to (SCOUT.md step 6b). It only ever CREATES documents: a role already in the
tracker is never rewritten, so his ticks and "not for me" marks are never overwritten.

  python campaign/scout/tracker.py rows <date> [--existing ids.txt] [--extra file.json]
  python campaign/scout/tracker.py learn <docs dir>   (an ArtifactData `list` of `jobs` saved with out_dir)
      -> his "US only" marks put those companies on seeker_feedback.json, so they're skipped from then on
      -> (rows) writes one JSON file per new role under campaign/scout/tracker/new/<date>/ and prints the ArtifactData
         `batch` writes (op "set", collection "jobs", file_path ...), in chunks of at most 50.

Sources for <date>: seeker/<date>.json (LinkedIn Jobs: final/lean apply or maybe), the startup-board posts seeker.py
adds to his digest, linkedin_posts/<date>.json (his LinkedIn posts search: `posts`, not `startups`), linkedin_posts/
picks_<date>.json (his own picks), and an optional --extra list in the tracker's own row shape. Startups proposed to
add-vee aren't rows unless they're also on his list.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seeker  # noqa: E402

URL = "https://claude.ai/artifact/7idQXkKrxYLBpAkVBSdFhj"
FIELDS = ("role", "company", "location", "terms", "how", "link", "post", "source", "added", "lean", "note")


def doc_id(r):
    key = (r.get("post") or r.get("link") or "") + "|" + (r.get("role") or "").lower() + "@" + (r.get("company") or "").lower()
    return "j" + hashlib.sha1(key.encode()).hexdigest()[:15]


def same_role(r):
    return re.sub(r"\W+", " ", ((r.get("role") or "") + " @ " + (r.get("company") or "")).lower()).strip()


def first_https(s):
    m = re.search(r"https://[^\s)>\]\"'·,]+", s or "")
    return m.group(0).rstrip(".") if m else None


def excluded(r):
    names = [c["company"].lower() for c in seeker.feedback().get("not_eligible_companies", [])]
    where = f"{r.get('location') or ''} {r.get('terms') or ''}"
    return any(n in (r.get("company") or "").lower() for n in names) or bool(seeker.ASIA.search(where)) \
        or bool(seeker.ASIA_TEXT.search(where))


def rows_for(day, extra=None):
    out = []
    p = seeker.OUT / f"{day}.json"
    if p.exists():
        d = json.loads(p.read_text())
        for x in d["posts"]:
            v = x.get("final") or x["screen"]["lean"]
            if v in ("apply", "maybe"):
                out.append({"role": x["title"], "company": x["company"], "location": x.get("location"),
                            "terms": x.get("note") or "; ".join(x["screen"]["why"]), "link": x.get("apply_url"),
                            "post": None, "source": "linkedin_jobs", "added": day, "lean": v})
        boards, _ = seeker.board_posts(day, d["posts"])
        for x in boards:
            out.append({"role": x["title"], "company": x["company"], "location": x.get("location"),
                        "terms": "From a startup job board; location terms not read: open the post.", "link": x["url"],
                        "source": "board", "added": day, "lean": "maybe"})
    lp = HERE / "linkedin_posts" / f"{day}.json"
    if lp.exists():
        d = json.loads(lp.read_text())
        for x in (d.get("posts", []) if isinstance(d, dict) else d):
            if x.get("lean") not in ("apply", "maybe"):
                continue
            out.append({"role": x.get("role"), "company": x.get("company"), "location": None,
                        "terms": x.get("location_terms"), "how": x.get("how_to_apply"),
                        "link": first_https(x.get("how_to_apply")), "post": x.get("post_url"),
                        "source": "linkedin_posts", "added": day, "lean": x["lean"], "note": x.get("note")})
    pk = HERE / "linkedin_posts" / f"picks_{day}.json"
    if pk.exists():
        for x in json.loads(pk.read_text()):
            out.append({"role": x.get("role"), "company": x.get("company"), "location": None,
                        "terms": f"{x.get('work_type') or ''}; {x.get('location_terms') or ''}".strip("; "),
                        "how": None, "link": first_https(x.get("note")), "post": x.get("post_url"), "source": "pick",
                        "added": day, "lean": x.get("lean", "apply"), "note": x.get("status")})
    out += extra or []
    seen, keep = set(), []
    for r in out:
        if excluded(r) or same_role(r) in seen:
            continue
        seen.add(same_role(r))
        r = {k: r.get(k) for k in FIELDS if r.get(k) not in (None, "")}
        r.update({"applied": False, "hidden": False})
        keep.append(r)
    return keep


def learn(docs_dir):
    """His "didn't apply" marks in the tracker feed the screening (sponsor, 2026-11-25). A role marked "US only" puts
    its company on seeker_feedback.json's not_eligible_companies ("hires US only"), so later posts from it are skipped
    by seeker.py and by the LinkedIn posts search. "Not for me" is recorded but changes no rule. Returns what was added."""
    fb_path = seeker.FEEDBACK
    fb = json.loads(fb_path.read_text()) if fb_path.exists() else {"not_eligible_companies": []}
    have = {c["company"].lower() for c in fb.get("not_eligible_companies", [])}
    added = []
    for f in sorted(Path(docs_dir).rglob("*.json")):
        d = json.loads(f.read_text())
        d = d.get("data", d)
        name = (d.get("company") or "").strip()
        if d.get("skip_reason") != "us_only" or not name or name.lower() in have:
            continue
        if re.search(r"unnamed|confidential|a startup \(", name, re.I):
            continue  # no real company name to block
        fb.setdefault("not_eligible_companies", []).append(
            {"company": name, "why": f"hires US only (sponsor's mark in the tracker, {d.get('skipped_at') or 'undated'}: "
                                     f"{d.get('role') or 'role'})"})
        have.add(name.lower())
        added.append(name)
    fb_path.write_text(json.dumps(fb, indent=2, ensure_ascii=False) + "\n")
    return added


def main(argv=None):
    a = argparse.ArgumentParser()
    sub = a.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rows")
    r.add_argument("date")
    r.add_argument("--existing", help="file with the tracker's current doc ids, one per line")
    r.add_argument("--extra", help="JSON list of extra rows in the tracker's shape")
    lr = sub.add_parser("learn")
    lr.add_argument("docs_dir", help="out_dir of an ArtifactData list of the jobs collection")
    a = a.parse_args(argv)
    if a.cmd == "learn":
        print(json.dumps({"added_to_not_eligible": learn(a.docs_dir)}))
        return
    existing = set(Path(a.existing).read_text().split()) if a.existing else set()
    extra = json.loads(Path(a.extra).read_text()) if a.extra else []
    rows = [x for x in rows_for(a.date, extra) if doc_id(x) not in existing]
    d = HERE / "tracker" / "new" / a.date
    d.mkdir(parents=True, exist_ok=True)
    writes = []
    for x in rows:
        f = d / f"{doc_id(x)}.json"
        f.write_text(json.dumps(x, indent=1, ensure_ascii=False) + "\n")
        writes.append({"op": "set", "collection": "jobs", "doc_id": doc_id(x), "file_path": str(f)})
    chunks = [writes[i:i + 50] for i in range(0, len(writes), 50)]
    print(json.dumps({"url": URL, "new_rows": len(rows), "batches": chunks}, indent=1))


if __name__ == "__main__":
    main()
