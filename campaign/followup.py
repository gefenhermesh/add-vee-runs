#!/usr/bin/env python3
"""Follow-up engine: thread state, the hard rules, and when a decision is due. Deterministic; no writing, no judgment.

Design: campaign/FOLLOWUPS.md (approved by the sponsor 2026-11-20). Three layers:
  1. this script: what is never allowed, and *when* a decision is due;
  2. the follow-up strategist (an agent session on add-vee, docs/campaign/followup-strategist.md): whether, who,
     which type, which angle, when, and the draft;
  3. the reviewer + live-check gate, then the sponsor, who sends every email by hand.

State lives in campaign/state.json -> prospects[].threads[] (one thread per contact person).

Commands (all print JSON or one line; all take --at <ISO> for tests):
  sent <slug> --email E --contact NAME --role R --thread GMAIL_THREAD --message MSG_ID [--kind email1|committee]
                                       [--weekend sat,sun]      email 1 (or the committee email) was sent
  step-sent <slug> <thread_id> --type V|N|T|L --message MSG_ID   a follow-up in that thread was sent
  reply <slug> <thread_id> --class C [--until ISO]               a reply came in (stops the company's sequence,
                                                                 except ooo -> wait until --until; bounce -> stop that thread)
  due                                                            decisions due now (start a strategist for each)
  start <slug> <thread_id|committee> --session S                 a strategist session was started for it
  pending                                                        strategist sessions to check
  decided <slug> <thread_id|committee> --decision send|wait|stop [--type T] [--draft-id D] [--until ISO] [--reason R]
  prompt <slug> <thread_id|committee>                            the strategist session's prompt
  show                                                           one line per thread

Hard rules (methodology section 5, sponsor-approved):
  - nothing is sent automatically; drafts only;
  - any human reply from the company stops every thread at that company;
  - at most MAX_FOLLOWUPS follow-ups per person and MAX_PEOPLE people per company; never restart after a "no";
  - never two emails to the same company on the same day;
  - a decision is due no sooner than GAP_BUSINESS_DAYS business days (recipient's weekend) after the last touch.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "campaign" / "state.json"
LOG = ROOT / "campaign" / "log.md"

MAX_FOLLOWUPS = 2          # per person, after their first email
MAX_PEOPLE = 2             # per company
GAP_BUSINESS_DAYS = 4      # minimum business days between touches at one company
PENDING_STALE_HOURS = 24   # a strategist session older than this is reported as stale
TYPES = {"V", "N", "T", "L"}
HUMAN_REPLIES = {"positive", "report_request", "objection", "not_now", "referral", "negative", "unsubscribe"}
REPLY_CLASSES = HUMAN_REPLIES | {"ooo", "bounce", "auto"}
DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

STRATEGIST_PROMPT = """You are the add-vee follow-up strategist for {company} ({domain}), slug `{slug}`, decision {key}.
Read docs/campaign/followup-strategist.md in this repository and follow it exactly. Work on branch `{branch}`
(`git fetch origin {branch} && git checkout {branch}`); the audit output is in output/{slug}/.
Write your decision to output/{slug}/followups/{step_dir}/ and save it with
`python scripts/save_output.py {slug} -m "follow-up decision {key}"`. Never send email or contact anyone.

The thread so far (from the campaign manager; dates UTC):
{facts}

What the campaign has learned so far (learn.py report, small numbers, read with care):
{learning}"""


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse(ts):
    if not ts:
        return None
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def iso(t):
    return t.isoformat(timespec="seconds")


def load():
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(state):
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def log(line, at):
    if not LOG.exists():
        return
    s = LOG.read_text(encoding="utf-8")
    entry = f"- {iso(at)} {line}\n"
    s = s.replace("\n## Cohorts", entry + "\n## Cohorts", 1) if "\n## Cohorts" in s else s + entry
    LOG.write_text(s, encoding="utf-8")


def prospect(state, slug):
    for p in state["prospects"]:
        if p["slug"] == slug:
            return p
    sys.exit(f"no prospect {slug}")


def thread(p, tid):
    for t in p.get("threads", []):
        if t["id"] == tid:
            return t
    sys.exit(f"no thread {tid} for {p['slug']}")


def business_days_between(a, b, weekend):
    """Whole business days from a's date to b's date (b later), skipping the recipient's weekend."""
    n, d = 0, a.date()
    while d < b.date():
        d += dt.timedelta(days=1)
        if d.weekday() not in weekend:
            n += 1
    return n


def touches(p):
    """Every send to this company: (time, thread_id)."""
    out = []
    for t in p.get("threads", []):
        out.append((parse(t["sent_at"]), t["id"]))
        out += [(parse(s["sent_at"]), t["id"]) for s in t.get("steps", []) if s.get("sent_at")]
    return sorted(x for x in out if x[0])


def sent_steps(t):
    return [s for s in t.get("steps", []) if s.get("sent_at")]


def open_draft(t):
    return next((s for s in t.get("steps", []) if s.get("draft_id") and not s.get("sent_at")), None)


def company_stopped(p):
    return any(t.get("status") == "replied" for t in p.get("threads", []))


def due(state, at):
    """Decisions due now. Deterministic: only *whether a decision is due*, never what it is."""
    out = []
    for p in state["prospects"]:
        threads = p.get("threads", [])
        if not threads or company_stopped(p):
            continue
        weekend = set(threads[0].get("weekend", [5, 6]))
        tl = touches(p)
        last = tl[-1][0] if tl else None
        if last and (last.date() == at.date() or business_days_between(last, at, weekend) < GAP_BUSINESS_DAYS):
            continue  # too soon after the last email to this company (any person)
        busy = (any(t.get("pending") or open_draft(t) for t in threads)
                or p.get("committee_pending") or p.get("committee_draft"))
        if busy:
            continue
        live, waiting = [], False
        for t in threads:
            if t.get("status", "active") != "active":
                continue
            if len(sent_steps(t)) >= MAX_FOLLOWUPS:
                continue
            if t.get("defer_until") and parse(t["defer_until"]) > at:
                waiting = True  # still this person's turn, just not yet (out of office, or the strategist said wait)
                continue
            live.append(t)
        if waiting and not live:
            continue
        if live:
            t = live[0]
            out.append({"slug": p["slug"], "key": t["id"], "step": len(sent_steps(t)) + 1,
                        "contact": t["contact"], "role": t["role"], "last_touch": iso(last)})
        elif len(threads) < MAX_PEOPLE and not p.get("committee_done") and all(
                t.get("status") in ("active", "stopped") for t in threads):
            if p.get("committee_defer_until") and parse(p["committee_defer_until"]) > at:
                continue
            out.append({"slug": p["slug"], "key": "committee", "step": 0, "contact": None, "role": None,
                        "last_touch": iso(last)})
    return out


def cmd_sent(a, state, at):
    p = prospect(state, a.slug)
    threads = p.setdefault("threads", [])
    if company_stopped(p):
        sys.exit(f"{a.slug}: the company replied; the sequence is stopped")
    if any(t["email"].lower() == a.email.lower() for t in threads):
        sys.exit(f"{a.slug}: {a.email} already has a thread")
    if len(threads) >= MAX_PEOPLE:
        sys.exit(f"{a.slug}: already {MAX_PEOPLE} people; rule says no more")
    sent = parse(a.at_sent) if a.at_sent else at
    if any(t0.date() == sent.date() for t0, _ in touches(p)):
        sys.exit(f"{a.slug}: another email went to this company the same day; rule says one per day")
    weekend = [DAYS[d.strip()] for d in a.weekend.split(",")] if a.weekend else [5, 6]
    tid = f"{a.slug}/{len(threads) + 1}"
    threads.append({"id": tid, "kind": a.kind, "contact": a.contact, "email": a.email, "role": a.role,
                    "gmail_thread_id": a.thread, "last_message_id": a.message, "sent_at": iso(sent),
                    "weekend": weekend, "steps": [], "status": "active"})
    if a.kind == "committee":
        p["committee_done"] = True
        p.pop("committee_pending", None)
        p.pop("committee_draft", None)
    log(f"followup: {tid} {a.kind} sent to {a.role}", at)
    print(json.dumps({"thread": tid}))


def cmd_step_sent(a, state, at):
    p = prospect(state, a.slug)
    t = thread(p, a.thread_id)
    sent = parse(a.at_sent) if a.at_sent else at
    d = open_draft(t)
    if d is None:
        d = {"n": len(t["steps"]) + 1, "type": a.type}
        t["steps"].append(d)
    d.update(type=a.type or d.get("type"), sent_at=iso(sent), message_id=a.message)
    t["last_message_id"] = a.message or t.get("last_message_id")
    log(f"followup: {a.thread_id} step {d['n']} ({d['type']}) sent", at)
    print(json.dumps({"thread": a.thread_id, "step": d["n"]}))


def cmd_reply(a, state, at):
    p = prospect(state, a.slug)
    t = thread(p, a.thread_id)
    t["reply"] = {"class": a.cls, "at": iso(at)}
    if a.cls == "ooo":
        if not a.until:
            sys.exit("ooo needs --until (their return date)")
        t["defer_until"] = a.until
    elif a.cls == "bounce":
        t["status"] = "stopped"
        t["stop_reason"] = "bounce"
    elif a.cls in HUMAN_REPLIES:
        t["status"] = "replied"
        for other in p["threads"]:
            if other is not t and other.get("status") == "active":
                other["status"] = "stopped"
                other["stop_reason"] = f"company replied on {t['id']}"
    log(f"followup: {a.thread_id} reply {a.cls}", at)
    human = a.cls in HUMAN_REPLIES
    print(json.dumps({"thread": a.thread_id, "class": a.cls, "notify_sponsor_now": human}))


def cmd_due(a, state, at):
    print(json.dumps(due(state, at), indent=1))


def target(p, key):
    return p if key == "committee" else thread(p, key)


def cmd_start(a, state, at):
    p = prospect(state, a.slug)
    rec = {"session_id": a.session, "started_at": iso(at)}
    if a.key == "committee":
        p["committee_pending"] = rec
    else:
        thread(p, a.key)["pending"] = rec
    log(f"followup: strategist started for {a.key} ({a.session})", at)
    print(json.dumps({"key": a.key, **rec}))


def cmd_pending(a, state, at):
    out = []
    for p in state["prospects"]:
        items = [("committee", p.get("committee_pending"))] + [(t["id"], t.get("pending")) for t in p.get("threads", [])]
        for key, rec in items:
            if rec:
                age_h = (at - parse(rec["started_at"])).total_seconds() / 3600
                out.append({"slug": p["slug"], "key": key, "session_id": rec["session_id"],
                            "branch": p.get("branch"), "age_hours": round(age_h, 1),
                            "stale": age_h > PENDING_STALE_HOURS})
    print(json.dumps(out, indent=1))


def cmd_decided(a, state, at):
    p = prospect(state, a.slug)
    if a.key == "committee":
        p.pop("committee_pending", None)
        if a.decision == "wait":
            p["committee_defer_until"] = a.until
        elif a.decision == "stop":
            p["committee_done"] = True
        elif a.decision == "send":
            p["committee_draft"] = {"draft_id": a.draft_id, "decided_at": iso(at), "reason": a.reason}
        log(f"followup: committee decision {a.decision} ({a.reason or ''})", at)
        print(json.dumps({"key": "committee", "decision": a.decision}))
        return
    t = thread(p, a.key)
    t.pop("pending", None)
    if a.decision == "send":
        if a.type not in TYPES:
            sys.exit(f"--type must be one of {sorted(TYPES)}")
        if len(sent_steps(t)) >= MAX_FOLLOWUPS:
            sys.exit(f"{a.key}: already {MAX_FOLLOWUPS} follow-ups; rule says no more")
        if t.get("status") != "active" or company_stopped(p):
            sys.exit(f"{a.key}: thread is {t.get('status')}; no follow-up")
        t["steps"].append({"n": len(t["steps"]) + 1, "type": a.type, "decided_at": iso(at),
                           "draft_id": a.draft_id, "reason": a.reason})
    elif a.decision == "wait":
        if not a.until:
            sys.exit("wait needs --until")
        t["defer_until"] = a.until
    elif a.decision == "stop":
        t["status"] = "stopped"
        t["stop_reason"] = a.reason or "strategist decided to stop"
    log(f"followup: {a.key} decision {a.decision} {a.type or ''} ({a.reason or ''})", at)
    print(json.dumps({"key": a.key, "decision": a.decision}))


def facts(p, key):
    lines = []
    for t in p.get("threads", []):
        lines.append(f"- {t['id']} ({t['kind']}): to {t['contact']}, {t['role']} <{t['email']}>, sent {t['sent_at']}, "
                     f"status {t.get('status')}" + (f", reply {t['reply']['class']}" if t.get("reply") else ""))
        for s in t.get("steps", []):
            lines.append(f"    step {s['n']} type {s['type']}: " + (f"sent {s['sent_at']}" if s.get("sent_at") else "drafted, not sent"))
    lines.append(f"- This decision: {'a committee email to a second person' if key == 'committee' else 'the next step in ' + key}.")
    sent = len(sent_steps(thread(p, key))) if key != "committee" else 0
    lines.append(f"- Rules: at most {MAX_FOLLOWUPS} follow-ups per person (this person has had {sent}), "
                 f"at most {MAX_PEOPLE} people per company, never after a reply.")
    return "\n".join(lines)


def cmd_prompt(a, state, at):
    p = prospect(state, a.slug)
    step = "committee" if a.key == "committee" else f"{a.key.split('/')[-1]}-{len(thread(p, a.key)['steps']) + 1}"
    learning = Path(a.learning).read_text(encoding="utf-8").strip() if a.learning else "(none yet)"
    print(STRATEGIST_PROMPT.format(company=p["company"], domain=p.get("domain", ""), slug=p["slug"], key=a.key,
                                   branch=p.get("branch") or f"campaign/{p['slug']}", step_dir=step,
                                   facts=facts(p, a.key), learning=learning))


def cmd_show(a, state, at):
    for p in state["prospects"]:
        for t in p.get("threads", []):
            steps = ",".join(f"{s['type']}{'' if s.get('sent_at') else '(draft)'}" for s in t.get("steps", []))
            print(f"{t['id']:<22} {t['role']:<10} {t.get('status'):<8} sent {t['sent_at'][:10]}  steps [{steps}]"
                  + (f"  reply {t['reply']['class']}" if t.get("reply") else "")
                  + ("  PENDING" if t.get("pending") else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--at", help="treat this ISO time as now (tests)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("sent"); x.add_argument("slug"); x.add_argument("--email", required=True)
    x.add_argument("--contact", required=True); x.add_argument("--role", required=True)
    x.add_argument("--thread", required=True); x.add_argument("--message", required=True)
    x.add_argument("--kind", choices=["email1", "committee"], default="email1")
    x.add_argument("--weekend", help="e.g. sat,sun (default) or fri,sat"); x.add_argument("--at-sent")
    x.set_defaults(fn=cmd_sent)
    x = sub.add_parser("step-sent"); x.add_argument("slug"); x.add_argument("thread_id")
    x.add_argument("--type", choices=sorted(TYPES)); x.add_argument("--message"); x.add_argument("--at-sent")
    x.set_defaults(fn=cmd_step_sent)
    x = sub.add_parser("reply"); x.add_argument("slug"); x.add_argument("thread_id")
    x.add_argument("--class", dest="cls", required=True, choices=sorted(REPLY_CLASSES)); x.add_argument("--until")
    x.set_defaults(fn=cmd_reply)
    x = sub.add_parser("due"); x.set_defaults(fn=cmd_due)
    x = sub.add_parser("start"); x.add_argument("slug"); x.add_argument("key"); x.add_argument("--session", required=True)
    x.set_defaults(fn=cmd_start)
    x = sub.add_parser("pending"); x.set_defaults(fn=cmd_pending)
    x = sub.add_parser("decided"); x.add_argument("slug"); x.add_argument("key")
    x.add_argument("--decision", required=True, choices=["send", "wait", "stop"]); x.add_argument("--type")
    x.add_argument("--draft-id"); x.add_argument("--until"); x.add_argument("--reason")
    x.set_defaults(fn=cmd_decided)
    x = sub.add_parser("prompt"); x.add_argument("slug"); x.add_argument("key")
    x.add_argument("--learning", help="file with learn.py report output"); x.set_defaults(fn=cmd_prompt)
    x = sub.add_parser("show"); x.set_defaults(fn=cmd_show)
    a = ap.parse_args(argv)
    at = parse(a.at) if a.at else now_utc()
    state = load()
    a.fn(a, state, at)
    if a.cmd in ("sent", "step-sent", "reply", "start", "decided"):
        save(state)


if __name__ == "__main__":
    main()
