#!/usr/bin/env python3
"""Refresh companies/<slug>/status.json from each company session's own add-vee branch.

  python campaign/fetch_status.py <sessions.json> [--add-vee ../add-vee]

sessions.json: {"<session_id>": {"status_bucket": ..., "branch": "<current add-vee branch from get_session>"}}.
Company sessions save output/<slug>/campaign_status.json on their branch (save_output.py). This reads it with
git (fetch + show), adds the branch, and writes companies/<slug>/status.json for tick.py. Read-only on add-vee.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sessions")
    p.add_argument("--add-vee", default=str(ROOT.parent / "add-vee"))
    a = p.parse_args()
    sessions = json.loads(Path(a.sessions).read_text())
    state = json.loads((ROOT / "campaign" / "state.json").read_text())
    for pr in state["prospects"]:
        sid = pr.get("session_id")
        info = sessions.get(sid or "", {})
        branch = info.get("branch") or pr.get("branch")
        if not sid or not branch:
            continue
        git(a.add_vee, "fetch", "-q", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
        r = git(a.add_vee, "show", f"origin/{branch}:output/{pr['slug']}/campaign_status.json")
        if r.returncode:
            print(f"{pr['slug']}: no campaign_status.json on {branch} yet")
            continue
        st = json.loads(r.stdout)
        st["branch"] = branch
        out = ROOT / "companies" / pr["slug"] / "status.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(st, indent=2) + "\n")
        print(f"{pr['slug']}: {st.get('stage')} ({branch})")


if __name__ == "__main__":
    main()
