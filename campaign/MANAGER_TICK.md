# The campaign manager tick

**Where it runs (learned in the pilot, 2026-11-19):** sessions started by automation (scheduled tasks, or sessions created by another session) get a reduced toolset: no Gmail, and no tools to start, check or message other sessions. So the manager is **one persistent "add-vee campaign manager" session that the sponsor opened from the app** (it has every tool), and an hourly scheduled task sends the tick into that same session. Each tick is short and reads its state from files, so the session's context grows slowly; automatic compaction handles the rest.

Company sessions need nothing but add-vee. They follow add-vee's `docs/campaign/company-session.md` and save everything on their own branch.

## Setup, once (in the new manager session)
1. The sponsor opens a **new session from the Claude app** with both repos (`add-vee`, `add-vee-runs`) and writes: *"You are the add-vee campaign manager. Read add-vee-runs/campaign/MANAGER_TICK.md and set yourself up."*
2. The manager checks it has `get_session`, `create_session`, `send_message`, Gmail (signed in as gefen@etico.cr) and `PushNotification`, and reports any that are missing.
3. It creates its own hourly scheduled task **bound to this same session** (`create_trigger` with no `persistent_session_id` and no `create_new_session_on_fire`; cron hourly; prompt: "Campaign tick: follow MANAGER_TICK.md → Each tick."). Then it runs the first tick right away.
4. It records its own session id and the trigger id in `state.json` → `manager`.

## Each tick
0. Make sure both repos are present: `add-vee-runs` (this one; push) and `add-vee` next to it (read only here). `git pull` this repo.
1. `python campaign/tick.py sessions`: the company session ids to check.
2. For each id, `get_session(id)`. Write `{ "<id>": {"status_bucket": ..., "branch": <external_metadata.current_branches[""]>} }` to `/tmp/sessions.json`.
3. `python campaign/fetch_status.py /tmp/sessions.json`: refreshes `companies/<slug>/status.json` from each company's branch.
4. `python campaign/tick.py plan /tmp/sessions.json`. **If it's empty and step 6 isn't due, reply "No changes." and stop.**
5. Carry out each action, in order:
   - `start`: `create_session(source_url, title, prompt, permission_mode "auto", tags ["add-vee-campaign", "company:<slug>"])`. Record `session_id`.
   - `nudge`: `send_message(session_id, message)`.
   - `draft`: in add-vee, `git fetch origin <branch>` and read `output/<slug>/outreach/` from it (`email_1.md`, `findings.jpg`, `plan.jpg`, `contacts.json`, `features.json`). Create **one Gmail draft** (Gmail must be gefen@etico.cr) with inline images (`cid:att0`, `cid:att1`) and a plain-text alternative. Address it to the primary contact **only if** `contacts.json` marks their email verified; otherwise to gefen@etico.cr itself, and mention that in the notification. Copy the outreach folder into `companies/<slug>/outreach/` here. Record `draft_id`. **Never send.**
   - `notify`: `PushNotification` with the message, and put it first in your reply.
   - `mark`: nothing to call.
6. **Once a day (first tick after 08:00 Israel time):** LEARNING.md → The loop, step 2. Log newly sent email-1 threads (`learn.py add` with `companies/<slug>/outreach/features.json` and the Gmail thread id), detect and classify replies (`learn.py outcome`), and **notify the sponsor immediately for any human reply**.
   **Once a week (Sunday's first tick):** `learn.py report`, the scout (SCOUT.md → Running the scout), `learn.py pick`, then notify the sponsor that the week's picks are ready to release.
7. Write `/tmp/results.json` (each action plus `"ok"`, plus `session_id` / `draft_id` where relevant, plus `error` if it failed). Run `python campaign/tick.py apply /tmp/results.json`, then commit and push.
8. Reply: the notification lines first, then one line per other action. Nothing else.

## Never
- Never send email or contact anyone. Drafts only; the sponsor sends.
- Never start a company that isn't `queued`. The sponsor releases companies (`held`/`proposed` → `queued`).
- Never do a company's audit work in the manager session.
