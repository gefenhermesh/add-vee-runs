#!/usr/bin/env python3
"""The scout's queue: every lead waits here until a run takes it in a batch (SCOUT.md, "slowly and deep").

  python campaign/scout/scout_queue.py add-longlist                       queue new companies from longlist.json
  python campaign/scout/scout_queue.py add "<name>" --source S [--note N] [--b2b yes|no] [--trigger-date YYYY-MM-DD]
  python campaign/scout/scout_queue.py batch [n]                          take the next n (default 15) for this run
  python campaign/scout/scout_queue.py hold "<name>" "<note>"             back to the queue after a light check
  python campaign/scout/scout_queue.py drop "<name>" "<reason>"           a clear non-match (SCOUT.md "Who fits")
  python campaign/scout/scout_queue.py recon "<name>" "<why>"             light check says recon; waits, ranked, for room
  python campaign/scout/scout_queue.py done "<name>" <slug>               recon'd: companies/<slug>/scout.json exists
  python campaign/scout/scout_queue.py status                            how clean the table is: counts per status
  python campaign/scout/scout_queue.py list [status]                      show the queue

Order of a batch: B2B (or unknown) before non-B2B, then a fresh trigger (within 60 days), then the oldest lead.
Companies already in state.json are never queued twice.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q = HERE / "queue.json"
FRESH_DAYS = 60


def key(name):
    n = re.sub(r"\(.*?\)", "", name or "").lower()
    n = re.sub(r"\b(security|technologies|technology|inc|ltd|ai|io|labs|computing)\b|[^a-z0-9א-ת ]", " ", n)
    return re.sub(r"\s+", " ", n).strip() or (name or "").lower()


def load():
    return json.loads(Q.read_text()) if Q.exists() else {"items": []}


def save(q):
    Q.write_text(json.dumps(q, indent=1, ensure_ascii=False) + "\n")


def known():
    st = json.loads((ROOT / "campaign" / "state.json").read_text())
    return {key(p.get("company") or p["slug"]) for p in st["prospects"]} | {key(p["slug"].replace("-", " ")) for p in st["prospects"]}


def find(q, name):
    k = key(name)
    for it in q["items"]:
        if it["key"] == k:
            return it
    sys.exit(f"not in queue: {name}")


def add(q, name, source, note=None, b2b=None, trigger_date=None, today=None):
    today = today or dt.date.today().isoformat()
    k = key(name)
    if k in known():
        return None
    for it in q["items"]:
        if it["key"] == k:
            if source not in it["sources"]:
                it["sources"].append(source)
            if trigger_date and (not it.get("trigger_date") or trigger_date > it["trigger_date"]):
                it["trigger_date"] = trigger_date
            if note:
                it["notes"].append(f"{today}: {note}")
            return it
    it = {"name": name, "key": k, "sources": [source], "added": today, "status": "queued", "b2b": b2b,
          "trigger_date": trigger_date, "notes": [f"{today}: {note}"] if note else [], "slug": None}
    q["items"].append(it)
    return it


def order(items, today):
    def fresh(it):
        t = it.get("trigger_date")
        try:
            return (dt.date.fromisoformat(today) - dt.date.fromisoformat(t)).days <= FRESH_DAYS
        except (TypeError, ValueError):
            return False
    return sorted(items, key=lambda it: (it.get("b2b") is False, not fresh(it), it["added"], it["name"].lower()))


def batch(q, n, today=None):
    today = today or dt.date.today().isoformat()
    waiting = [it for it in q["items"] if it["status"] in ("queued", "held")]
    picked = order(waiting, today)[:n]
    for it in picked:
        it["status"], it["batch"] = "in_batch", today
    return picked


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 2
    q, cmd = load(), a[1]
    if cmd == "add-longlist":
        ll = json.loads((HERE / "longlist.json").read_text())
        n = 0
        for c in ll["companies"]:
            if c.get("known"):
                continue
            dates = [s.get("date") for s in c["signals"] if s.get("signal") == "funding" and re.match(r"\d{4}-\d\d-\d\d", s.get("date") or "")]
            n += bool(add(q, c["company"], "+".join(sorted({s["source"] for s in c["signals"]})), trigger_date=max(dates) if dates else None))
        print(f"{n} added or merged")
    elif cmd == "add":
        opt = dict(zip(a[3::2], a[4::2]))
        b2b = {"yes": True, "no": False}.get(opt.get("--b2b"))
        print("added" if add(q, a[2], opt.get("--source", "manual"), opt.get("--note"), b2b, opt.get("--trigger-date")) else "already in state.json")
    elif cmd == "batch":
        for it in batch(q, int(a[2]) if len(a) > 2 else 15):
            print(f"{it['name']:28s} {','.join(it['sources']):30s} {it.get('trigger_date') or '':10s} {'; '.join(it['notes'])[:80]}")
    elif cmd in ("hold", "drop", "recon"):
        it = find(q, a[2])
        it["status"] = {"hold": "held", "drop": "dropped", "recon": "recon_ready"}[cmd]
        it["notes"].append(f"{dt.date.today().isoformat()}: {cmd}: {a[3]}")
    elif cmd == "done":
        it = find(q, a[2])
        it["status"], it["slug"] = "done", a[3]
    elif cmd == "status":
        from collections import Counter
        c = Counter(i["status"] for i in q["items"])
        left = c["queued"] + c["held"] + c["in_batch"]
        print(json.dumps({**c, "left_to_light_check": left, "clean": left == 0}))
    elif cmd == "list":
        for it in order([i for i in q["items"] if len(a) < 3 or i["status"] == a[2]], dt.date.today().isoformat()):
            print(f"{it['status']:9s} {it['name']:28s} {','.join(it['sources'])[:30]:30s} {(it['notes'] or [''])[-1][:70]}")
    else:
        print(__doc__)
        return 2
    save(q)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
