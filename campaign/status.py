#!/usr/bin/env python3
"""Company session progress report for the campaign manager.

  python ../add-vee-runs/campaign/status.py <slug> <stage> [--note "..."] [--branch BRANCH] [--draft-id ID]

Stages, in order: loop_a, waiting_gate_1_2, loop_b, report, loop_c, action_plan, outreach, done.
Writes companies/<slug>/status.json (stage, time, branch, note, draft id) and commits and pushes it,
so the hourly manager tick sees progress. Run it at every milestone, and right before stopping.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ["loop_a", "waiting_gate_1_2", "loop_b", "report", "loop_c", "action_plan", "outreach", "done"]


def git(*a, check=True):
    r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a)}: {r.stderr.strip()}")
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("stage", choices=STAGES)
    p.add_argument("--note", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--draft-id", default="")
    a = p.parse_args()
    f = ROOT / "companies" / a.slug / "status.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(f.read_text()) if f.exists() else {}
    new = {**old, "stage": a.stage, "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "note": a.note}
    if a.branch:
        new["branch"] = a.branch
    if a.draft_id:
        new["gmail_draft_id"] = a.draft_id
    f.write_text(json.dumps(new, indent=2) + "\n")
    git("add", str(f.relative_to(ROOT)))
    git("commit", "-q", "-m", f"status {a.slug}: {a.stage}")
    for i in range(4):
        git("pull", "-q", "--rebase", check=False)
        if git("-c", "push.negotiate=true", "push", "-q", check=False).returncode == 0:
            print(f"status: {a.slug} -> {a.stage} (pushed)")
            return 0
        time.sleep(2 ** (i + 1))
    print("status: committed but push failed; retry later", file=sys.stderr)
    return 4


if __name__ == "__main__":
    sys.exit(main())
