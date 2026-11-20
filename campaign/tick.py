#!/usr/bin/env python3
"""Campaign manager tick: decide what to do this hour, deterministically.

The hourly scheduled task starts a fresh, short session. That session (Claude) does three things:

  1. python campaign/tick.py sessions          -> prints the session ids to look up
     then calls get_session(id) for each one and saves {id: {"status_bucket": ..., "status": ...}} to a file
  2. python campaign/tick.py plan <sessions.json>   -> prints a JSON list of actions (and changes nothing)
     then carries out each action with its tools: create_session / send_message / notify
  3. python campaign/tick.py apply <results.json>   -> records what was done in state.json and log.md

All decisions are in this script, so the hourly session spends almost nothing when nothing changed:
"plan" returns an empty list and the session ends.

Inputs per company: campaign/state.json (the queue, owned by this script) and
companies/<slug>/status.json, refreshed each tick by campaign/fetch_status.py from the company session's own add-vee branch
(output/<slug>/campaign_status.json; see add-vee docs/campaign/company-session.md).

Rules (sponsor decisions, 2026-11-18/19):
- One company session works at a time (settings.max_concurrent_running). A company waiting at Gate 1-2
  for the sponsor doesn't count as working, so the next company can start its Loop A.
- Never send email. Company sessions only create Gmail drafts.
- Notify the sponsor (Claude app) only when they need to act: Gate 1-2 waiting, a draft is ready, a run is stuck.
- Watchdog: a working company session that's idle/failed with no progress for STALL_MIN minutes gets
  "continue" (at most MAX_NUDGES times), then it's marked stuck and the sponsor is told.

Exit codes: 0 ok, 2 usage error.
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "campaign" / "state.json"
LOG = ROOT / "campaign" / "log.md"
STALL_MIN = 90          # minutes without progress before a nudge
MAX_NUDGES = 2          # nudges before "stuck"
ACTIVE = {"starting", "running"}
WAITING_STAGES = {"waiting_gate_1_2"}
PAUSED_STAGES = {"paused_brightdata"}
JOB_EXPIRY_DAYS = 10  # an SEO-job company not started within this many days of its post date drops out (no backlog)  # stopped on purpose (sponsor pause): no nudge, no new starts
DONE_STAGES = {"done"}

ADD_VEE_REPO = "https://github.com/gefenhermesh/add-vee"

START_PROMPT = """You are a campaign company session for {company} ({domain}), slug `{slug}`.
Read docs/campaign/company-session.md in this repository and follow it exactly: run the full add-vee audit for
this company (CLAUDE.md, unchanged, including the Gate 1-2 stop), keep output/{slug}/campaign_status.json current,
and write the outreach material into output/{slug}/outreach/. You need no other repository and no Gmail.
Never send email or contact anyone."""

JOB_TRACK = """
Outreach track: seo_job. They're hiring for "{title}" ({url}, posted {posted}). Write the outreach as the sponsor's
"I'd love to be considered for this role" email: docs/campaign/company-session.md -> "Track seo_job"."""

NUDGE_PROMPT = """Campaign manager check: this session looks idle with the run unfinished (last progress {age} min ago).
If you stopped on a usage limit or an error, continue now: run `python scripts/run_ledger.py status {slug}` and
resume from the recorded resume point (COMPANY_SESSION.md, "Resuming"). If you're waiting for the sponsor at
Gate 1-2, make sure companies/{slug}/status.json says stage "waiting_gate_1_2" and stop again."""


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def load_state():
    s = json.loads(STATE.read_text())
    s.setdefault("settings", {})
    s["settings"].setdefault("max_concurrent_running", s["settings"].pop("max_concurrent_company_sessions", 1))
    s.setdefault("prospects", [])
    return s


def company_status(slug):
    p = ROOT / "companies" / slug / "status.json"
    return json.loads(p.read_text()) if p.exists() else {}


def plan(state, sessions, now):
    actions = []
    running = 0
    for p in state["prospects"]:  # SEO-job finds go stale fast: expire the ones never started in time
        posted = (p.get("job") or {}).get("posted")
        if p.get("track") == "seo_job" and p.get("status") in ("proposed", "queued") and posted:
            try:
                age = (now.date() - dt.date.fromisoformat(posted[:10])).days
            except ValueError:
                continue
            if age > JOB_EXPIRY_DAYS:
                actions.append({"do": "mark", "slug": p["slug"], "status": "expired",
                                "reason": f"job post {age} days old, never started"})
    for p in state["prospects"]:
        st = p.get("status")
        if st not in ACTIVE | {"waiting_gate", "paused"}:
            continue
        cs = company_status(p["slug"])
        stage = cs.get("stage")
        progress = parse(cs.get("ts")) or parse(p.get("started_at"))
        age = int((now - progress).total_seconds() // 60) if progress else None
        sess = sessions.get(p.get("session_id") or "", {})
        bucket = (sess.get("status_bucket") or "").lower().removeprefix("session_status_bucket_") or None  # get_session returns SESSION_STATUS_BUCKET_X
        notified = p.get("notified", {})

        if stage in DONE_STAGES:
            actions.append({"do": "mark", "slug": p["slug"], "status": "done"})
            if not p.get("gmail_draft_id"):
                actions.append({"do": "draft", "slug": p["slug"], "branch": cs.get("branch"),
                                "outreach_dir": f"output/{p['slug']}/outreach/"})
            if not notified.get("done"):
                actions.append({"do": "notify", "slug": p["slug"], "kind": "done",
                                "message": f"{p['company']}: audit done, outreach draft in Gmail (gefen@etico.cr) for your review"})
            continue
        if stage in PAUSED_STAGES:
            if st != "paused":
                actions.append({"do": "mark", "slug": p["slug"], "status": "paused"})
            continue
        if stage in WAITING_STAGES:
            if st != "waiting_gate":
                actions.append({"do": "mark", "slug": p["slug"], "status": "waiting_gate"})
            if not notified.get("gate"):
                actions.append({"do": "notify", "slug": p["slug"], "kind": "gate",
                                "message": f"{p['company']}: Gate 1-2 ready. Reply \"approve {p['slug']}\" or what to change"})
            continue
        if st in ("waiting_gate", "paused"):
            # The company moved past the gate (the sponsor approved): it's working again.
            actions.append({"do": "mark", "slug": p["slug"], "status": "running"})
        running += 1
        if bucket == "blocked" and not notified.get("blocked"):
            actions.append({"do": "notify", "slug": p["slug"], "kind": "blocked",
                            "message": f"{p['company']}: session is blocked waiting for input (not the gate). Please check it"})
        stalled = bucket in ("idle", "failed", "completed", "review_ready") and (age is None or age >= STALL_MIN)
        if stalled:
            if p.get("nudges", 0) < MAX_NUDGES:
                actions.append({"do": "nudge", "slug": p["slug"], "session_id": p.get("session_id"),
                                "message": NUDGE_PROMPT.format(age=age if age is not None else "?", slug=p["slug"])})
            else:
                actions.append({"do": "mark", "slug": p["slug"], "status": "stuck"})
                if not notified.get("stuck"):
                    actions.append({"do": "notify", "slug": p["slug"], "kind": "stuck",
                                    "message": f"{p['company']}: run stuck after {MAX_NUDGES} nudges (stage {stage or '?'}). Needs you"})
                running -= 1

    if state["settings"].get("brightdata_paused"):
        return actions  # audits need Bright Data: start nothing new until the sponsor resumes payment
    cap = state["settings"]["max_concurrent_running"]
    order = sorted(state["prospects"], key=lambda p: -int(p.get("priority") or 0))  # SEO-job finds first; stable otherwise
    for p in order:
        if running >= cap:
            break
        if p.get("status") == "queued":
            actions.append({"do": "start", "slug": p["slug"], "source_url": ADD_VEE_REPO,
                            "title": f"add-vee campaign: {p['company']}",
                            "prompt": START_PROMPT.format(company=p["company"], domain=p.get("domain", ""), slug=p["slug"])
                            + (JOB_TRACK.format(**p["job"]) if p.get("track") == "seo_job" else "")})
            running += 1
    return actions


def apply(state, results, now):
    ts = now.isoformat(timespec="seconds")
    by = {p["slug"]: p for p in state["prospects"]}
    lines = []
    for r in results:
        p = by.get(r.get("slug"))
        if not p:
            continue
        ok = r.get("ok", True)
        if r["do"] == "start" and ok:
            p.update(status="starting", session_id=r["session_id"], started_at=ts, nudges=0, notified={})
        elif r["do"] == "nudge" and ok:
            p["nudges"] = p.get("nudges", 0) + 1
        elif r["do"] == "mark":
            p["status"] = r["status"]
            if r["status"] == "running":
                p["nudges"] = 0
        elif r["do"] == "draft" and ok:
            p["gmail_draft_id"] = r.get("draft_id")
        elif r["do"] == "notify" and ok:
            p.setdefault("notified", {})[r["kind"]] = ts
        lines.append(f"- {ts} {r['do']} {r.get('slug')}" + (f" {r.get('status') or r.get('kind') or ''}".rstrip())
                     + ("" if ok else f" FAILED: {r.get('error', '')}"))
    # a session that has written any progress is running, not starting
    for p in state["prospects"]:
        if p.get("status") == "starting" and company_status(p["slug"]).get("stage"):
            p["status"] = "running"
    state["last_tick"] = ts
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    if lines:
        log = LOG.read_text() if LOG.exists() else "# Campaign log\n\n## Ticks\n\n## Cohorts\n"
        log = log.replace("## Ticks\n", "## Ticks\n" + "\n".join(lines) + "\n", 1)
        LOG.write_text(log)
    return lines


def main(argv):
    if len(argv) < 2 or argv[1] not in {"sessions", "plan", "apply"}:
        print(__doc__)
        return 2
    state = load_state()
    if argv[1] == "sessions":
        ids = [p["session_id"] for p in state["prospects"]
               if p.get("session_id") and p.get("status") in ACTIVE | {"waiting_gate"}]
        print(json.dumps(ids))
        return 0
    if len(argv) < 3:
        print(f"usage: tick.py {argv[1]} <file.json>")
        return 2
    data = json.loads(Path(argv[2]).read_text())
    now = parse(argv[3]) if len(argv) > 3 else now_utc()
    if argv[1] == "plan":
        print(json.dumps(plan(state, data, now), indent=1, ensure_ascii=False))
    else:
        for line in apply(state, data, now):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
