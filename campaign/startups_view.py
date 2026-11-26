#!/usr/bin/env python3
"""Startups tab data for the sponsor's job-applications page (sponsor, 2026-11-26: "startup roles need to be
prioritized in add-vee and not be swallowed in the job applications board ... a clear view on startup roles and
add-vee runs they need and when and where they are in the queue").

One row per company on the SEO-job track (`track: seo_job` in state.json), whatever its status, with: the role and
its post, the add-vee stage in plain words, the queue position, the email and follow-up state, the next step and
who owns it, and the audit's links. Deterministic; reads state.json, campaign/board/board.json and each company's
outreach brief. Writes campaign/scout/tracker/startups.json, published next to the tracker page.

  python campaign/startups_view.py
"""
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "scout", "tracker", "startups.json")

RUNNING = {"running", "released", "waiting_gate", "paused"}


def links_for(slug):
    out = {}
    for name in ("brief.json",):
        p = os.path.join(ROOT, "companies", slug, "outreach", name)
        if os.path.exists(p):
            b = json.load(open(p))
            for k in ("links", "artifacts", "deliverables"):
                if isinstance(b.get(k), dict):
                    out.update(b[k])
    st = os.path.join(ROOT, "companies", slug, "status.json")
    if os.path.exists(st):
        s = json.load(open(st))
        for k, v in s.items():
            if isinstance(v, str) and v.startswith("https://claude.ai/artifact/"):
                out.setdefault(k.replace("_url", ""), v)
    norm = {}
    for k, v in out.items():
        if not (isinstance(v, str) and v.startswith("https://")):
            continue
        key = {"visibility_report": "report", "research_story": "story"}.get(k, k)
        norm[key] = v
    return {k: norm[k] for k in ("report", "action_plan", "scope", "story") if k in norm}


def queue_order(state):
    """Same order tick.py releases and starts work: gate-approved first (by approval time), then queued by priority."""
    ps = state["prospects"]
    urgent = sorted((p for p in ps if p.get("status") == "queued" and int(p.get("priority") or 0) >= 10),
                    key=lambda p: (-int(p.get("priority") or 0), p.get("queue_rank") or 999))
    approved = sorted((p for p in ps if p.get("status") == "approved_waiting"),
                      key=lambda p: ((p.get("gate_approval") or {}).get("ts") or "", (p.get("gate_approval") or {}).get("order", 0)))
    queued = sorted((p for p in ps if p.get("status") == "queued" and int(p.get("priority") or 0) < 10),
                    key=lambda p: (-int(p.get("priority") or 0), p.get("queue_rank") or 999))
    return [p["slug"] for p in urgent + approved + queued]


def main():
    state = json.load(open(os.path.join(HERE, "state.json")))
    board_p = os.path.join(HERE, "board", "board.json")
    board = json.load(open(board_p)) if os.path.exists(board_p) else {"rows": []}
    threads = {r["slug"]: r for r in board["rows"]}
    order = queue_order(state)
    hold = state["settings"].get("hold_new_work_until")
    now = dt.datetime.now(dt.timezone.utc)
    held = bool(hold and dt.datetime.fromisoformat(hold.replace("Z", "+00:00")) > now)
    rows = []
    for p in state["prospects"]:
        if p.get("track") != "seo_job" or p.get("status") == "withdrawn":
            continue
        slug, st = p["slug"], p.get("status")
        job = p.get("job") or {}
        group, stage, nxt, owner = "", "", "", ""
        pos = order.index(slug) + 1 if slug in order else None
        if st == "proposed":
            group, stage = "release", "Found and checked, audit not started"
            nxt, owner = f'Reply "release {slug}" to start its audit', "you"
        elif st in ("queued", "approved_waiting"):
            group = "queue"
            stage = "Gate 1-2 approved, waiting its turn" if st == "approved_waiting" else "Released, waiting to start"
            when = f"after the usage hold ends ({hold[:16].replace('T', ' ')} UTC)" if held else "when the running audit finishes"
            nxt, owner = f"#{pos} in the queue, starts {when}", "campaign"
        elif st in RUNNING or p.get("stage") in ("loop_a", "loop_b", "loop_c"):
            group, stage = "running", f"Audit running ({p.get('stage') or st})"
            nxt, owner = "Gate 1-2 needs your approval" if st == "waiting_gate" else "Audit in progress", "you" if st == "waiting_gate" else "campaign"
        elif st in ("done", "sent"):
            t = threads.get(slug)
            if t:
                group = "outreach"
                stage = f"Email 1 sent {t['sent_at']}"
                nxt = t["action"]
                owner = "you" if t["state"] in ("you_send", "replied") else "campaign"
            else:
                group, stage = "email_ready", "Audit done, email 1 drafted in Gmail"
                nxt, owner = p.get("draft_note") or "Verify the address, then send email 1 from Gmail", "you"
        else:
            group, stage, nxt, owner = "other", st or "", "", ""
        rows.append({
            "slug": slug, "company": p.get("company") or slug, "domain": p.get("domain"),
            "role": job.get("title"), "job_url": job.get("url"), "location": job.get("location"),
            "posted": (job.get("posted") or "")[:10], "group": group, "stage": stage,
            "queue_position": pos, "next": nxt, "owner": owner, "links": links_for(slug),
            "apply_note": "Apply after email 1 goes out" if group in ("queue", "running", "release", "email_ready") else
                          ("Email 1 is out: apply now if you haven't" if group == "outreach" else ""),
            "reason": (p.get("reason") or "")[:280],
        })
    gorder = {"email_ready": 0, "running": 1, "queue": 2, "release": 3, "outreach": 4, "other": 5}
    rows.sort(key=lambda r: (gorder.get(r["group"], 9), r["queue_position"] or 99, r["company"].lower()))
    data = {"updated_at": now.isoformat(timespec="seconds"), "hold_until": hold if held else None, "rows": rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), indent=1)
    c = {}
    for r in rows:
        c[r["group"]] = c.get(r["group"], 0) + 1
    print(f"startups: {len(rows)} {c}")


if __name__ == "__main__":
    main()
