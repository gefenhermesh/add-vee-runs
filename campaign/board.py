#!/usr/bin/env python3
"""Follow-up board: one row per outreach thread, plus email-1 drafts not yet sent (sponsor, 2026-11-26:
"due dates are passing ... I will start forgetting"). Writes campaign/board/board.json for the
"Outreach Board" artifact. Deterministic; reads state.json only. Run it in every daily block and after
any send, reply, draft or decision, then republish the artifact.

  python campaign/board.py            # writes campaign/board/board.json, prints a one-line summary
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import followup as fu  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "board", "board.json")


def next_due(last, weekend):
    """First date on which a decision is due: GAP_BUSINESS_DAYS business days after the last touch."""
    d = last
    while fu.business_days_between(last, d, weekend) < fu.GAP_BUSINESS_DAYS:
        d += dt.timedelta(days=1)
    return d.date().isoformat()


def build(state, at):
    rows, waiting_email1 = [], []
    for p in state["prospects"]:
        threads = p.get("threads", [])
        name = p.get("company") or p.get("name") or p["slug"]
        if not threads:
            if p.get("status") == "done" and p.get("draft_id"):
                waiting_email1.append({"company": name, "slug": p["slug"], "draft_id": p.get("draft_id"),
                                       "note": p.get("draft_note") or "email 1 drafted, waiting for a verified address"})
            continue
        weekend = set(threads[0].get("weekend", [5, 6]))
        tl = fu.touches(p)
        last = tl[-1][0] if tl else None
        stopped = fu.company_stopped(p)
        for t in threads:
            sent = fu.sent_steps(t)
            draft = fu.open_draft(t)
            st = t.get("status", "active")
            if st == "replied":
                state_, action = "replied", "Reply received: answer it yourself"
            elif st != "active":
                state_, action = st, "Closed"
            elif draft:
                state_, action = "you_send", f"Follow-up {draft.get('type','')} is drafted in Gmail: review and send"
            elif t.get("pending"):
                state_, action = "drafting", "Strategist is writing the next step"
            elif t.get("defer_until") and fu.parse(t["defer_until"]) > at:
                state_, action = "waiting", f"Waiting until {t['defer_until'][:10]}"
            elif len(sent) >= fu.MAX_FOLLOWUPS:
                state_, action = "done", "Both follow-ups sent"
            else:
                d = next_due(last, weekend) if last else None
                state_ = "due" if d and d <= at.date().isoformat() else "scheduled"
                action = "Next step due now" if state_ == "due" else f"Next step due {d}"
            rows.append({
                "company": name, "slug": p["slug"], "contact": t.get("contact"), "role": t.get("role"),
                "email": t.get("email"), "sent_at": (t.get("sent_at") or "")[:10],
                "followups_sent": len(sent), "max_followups": fu.MAX_FOLLOWUPS,
                "last_touch": last.date().isoformat() if last else None,
                "next_due": next_due(last, weekend) if (last and not stopped) else None,
                "state": state_, "action": action,
                "draft_id": draft.get("draft_id") if draft else None,
            })
    order = {"replied": 0, "you_send": 1, "due": 2, "drafting": 3, "waiting": 4, "scheduled": 5, "done": 6}
    rows.sort(key=lambda r: (order.get(r["state"], 9), r["next_due"] or "9999"))
    return {"updated_at": fu.iso(at), "rows": rows, "email1_waiting": waiting_email1}


def main():
    at = fu.now_utc()
    state = fu.load()
    board = build(state, at)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(board, f, indent=1)
    c = {}
    for r in board["rows"]:
        c[r["state"]] = c.get(r["state"], 0) + 1
    print(f"board: {len(board['rows'])} threads {c}; {len(board['email1_waiting'])} email-1 drafts unsent")


if __name__ == "__main__":
    main()
