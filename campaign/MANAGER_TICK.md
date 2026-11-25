# The campaign manager tick

**Where it runs (learned in the pilot, 2026-11-19):** sessions started by automation (scheduled tasks, or sessions created by another session) get a reduced toolset: no Gmail, and no tools to start, check or message other sessions. So the manager is **one persistent "add-vee campaign manager" session that the sponsor opened from the app** (it has every tool), and an hourly scheduled task sends the tick into that same session. Each tick is short and reads its state from files, so the session's context grows slowly; automatic compaction handles the rest.

Company sessions need nothing but add-vee. They follow add-vee's `docs/campaign/company-session.md` and save everything on their own branch.

## Setup, once (in the new manager session)
1. The sponsor opens a **new session from the Claude app** with both repos (`add-vee`, `add-vee-runs`) and writes: *"You are the add-vee campaign manager. Read add-vee-runs/campaign/MANAGER_TICK.md and set yourself up."*
1b. **Read `campaign/MANAGER_HANDOFF.md`** (the previous manager's note: current state, open items, lessons). If the campaign is paused there, set yourself up but don't create the hourly task until the sponsor resumes it.
2. The manager checks it has `get_session`, `create_session`, `send_message`, Gmail (signed in as gefen@etico.cr) and `PushNotification`, and reports any that are missing.
3. It creates its own hourly scheduled task **bound to this same session** (`create_trigger` with no `persistent_session_id` and no `create_new_session_on_fire`; cron hourly; prompt: "Campaign tick: follow MANAGER_TICK.md → Each tick."). Then it runs the first tick right away.
4. It records its own session id and the trigger id in `state.json` → `manager`.

## The sponsor talks only to this chat (sponsor decision, 2026-11-19)
Every decision the sponsor makes about a company happens here, never in the company's own session.

**When a company reaches Gate 1-2:** send **one line only**, both as the phone notification and in this chat: `<Company>: Gate 1-2 ready. Scope & Prompts <link>. Reply "approve <company>" or what to change.` Take the link from `get_session` → `external_metadata.artifacts`. **Never paste gate material, research coverage or summaries into this chat.** This session runs for weeks, so its context must stay small. The sponsor opens the company's own pages or session when they want detail.

**When the sponsor replies here** with an approval or changes for a company:
0. While `settings.one_at_a_time` is true and another audit is working, don't write the file yet: set the company's status to `approved_waiting` with `gate_approval: {ts, sponsor_words}`; `tick.py plan` releases it (`release_gate`) when it's its turn. Changes (not approval) go out at once.
1. In add-vee, check out the company's branch (`git fetch origin <branch> && git checkout <branch>`; never master).
2. Write `output/<slug>/gate_1_2_approval.json` (`{"decision": "approved", "sponsor_words": <their exact words>, "ts": <UTC now>, "via": "campaign manager session <this session's id>"}`), or `gate_1_2_feedback.json` with `"decision": "changes"`. Commit and push to that branch.
3. `send_message` to the company session: "Your Gate 1-2 decision file is on your branch (`output/<slug>/gate_1_2_…json`); follow docs/campaign/company-session.md → How the sponsor approves Gate 1-2." Add `git pull` and `git merge origin/master` hints if the session started before 2026-11-19 21:00 UTC.
4. Record it in `campaign/log.md`, and confirm to the sponsor in one line.

The company session's own instructions (add-vee `docs/campaign/company-session.md`, merged as PR #7) tell it to treat that file as the sponsor's decision. Never write an approval the sponsor didn't give in this chat.

## Bright Data pause (sponsor, 2026-11-20)
While `state.json` → `settings.brightdata_paused` is true: no Bright Data calls anywhere. `tick.py` starts no new company; running audits continue without Bright Data or stop at stage `paused_brightdata` (shown as `paused`, never nudged); scout budgets are 0 (`campaign/scout/budget.json` → `_paused`), so the jobs route reads free pages only and the cap-raise rule is suspended. **When the sponsor says payment is resumed:** set `brightdata_paused` to false, restore the caps from `_paused.resume_to` and remove `_paused`, then `send_message` each `paused` company session: "Bright Data is back (sponsor): resume from your paused step." One line to the sponsor.

## Each tick
0. Make sure both repos are present: `add-vee-runs` (this one; push) and `add-vee` next to it (read only here). `git pull` this repo.
1. `python campaign/tick.py sessions`: the company session ids to check.
2. For each id, `get_session(id)`. Write `{ "<id>": {"status_bucket": ..., "branch": <external_metadata.current_branches[""]>} }` to `/tmp/sessions.json`.
3. `python campaign/fetch_status.py /tmp/sessions.json`: refreshes `companies/<slug>/status.json` from each company's branch.
4. `python campaign/tick.py plan /tmp/sessions.json`. **If it's empty and step 6 isn't due, reply "No changes." and stop.**
5. Carry out each action, in order:
   - `start`: `create_session(source_url, title, prompt, permission_mode "auto", tags ["add-vee-campaign", "company:<slug>"])`. Record `session_id`.
   - `nudge`: `send_message(session_id, message)`.
   - `draft`: **first the live-check gate** (add-vee master, PR #8): with the company's branch checked out in add-vee, run `python scripts/narrative_check.py` on `output/<slug>/outreach/email_1.md`, `report_narrative.json` and `action_plan_narrative.json`. Any FAIL: don't create the draft; `send_message` the company session the FAIL lines ("check these live, record them in live_checks.json, fix and republish"), record the action as failed with the reason, and tell the sponsor in one line. Only when all three are clean: in add-vee, `git fetch origin <branch>` and read `output/<slug>/outreach/` from it (`email_1.md`, `findings.jpg`, `plan.jpg`, `contacts.json`, `features.json`). Create **one Gmail draft** (Gmail must be gefen@etico.cr) with inline images (`cid:att0`, `cid:att1`), a plain-text alternative and **`includeSignature: true`** (the sponsor's saved signature goes on every draft and every send, follow-ups included; sponsor, 2026-11-22). Address it to the primary contact **only if** `contacts.json` marks their email verified; otherwise to gefen@etico.cr itself, and mention that in the notification. Copy the outreach folder into `companies/<slug>/outreach/` here. Record `draft_id`. **Never send.**
   - `notify`: `PushNotification` with the message, and put it first in your reply.
   - `release_gate` (sponsor, 2026-11-25: one audit at a time): the sponsor already approved this company's Gate 1-2 in this chat (recorded in `state.json` → `gate_approval`) and it's now its turn. Do the approval steps from "When the sponsor replies here" with `sponsor_words` and `ts` from the action (plus its `note`, if any, in the message), then `send_message` the company session as usual.
   - `mark`: nothing to call.
6. **Once a day (first tick after 09:00 US Eastern, America/New_York, so about 09:32 ET; sponsor, 2026-11-25; it was 08:00 Israel time before): mail and follow-ups** (design: `FOLLOWUPS.md`; rules and state: `followup.py`).
   a. **Sent mail** (gefen@etico.cr, `in:sent newer_than:3d`, excluding the sponsor's own addresses): for each send to a prospect contact, match it to the company by recipient domain and subject.
      - A new email 1 (or a committee email): `followup.py sent <slug> --email … --contact … --role … --thread <gmail thread id> --message <message id> --at-sent <date> [--kind committee] [--weekend fri,sat for Israel-only recipients]`, and `learn.py add` with `companies/<slug>/outreach/features.json` + the thread id.
      - A follow-up sent in an existing thread: `followup.py step-sent <slug> <thread_id> --type <V|N|T|L> --message <message id> --at-sent <date>`, and `learn.py followup <slug>`.
   b. **Replies** in every open thread (`get_thread` each `gmail_thread_id`; anything from the company after our last message). Classify: positive, report_request, objection, not_now, referral, negative, unsubscribe, ooo (with the return date), bounce, auto. Record with `followup.py reply` and `learn.py outcome`. **Any human reply: notify the sponsor at once** (one line: company, who, class) and draft nothing. Unclear: ask the sponsor in one line instead of guessing.
   c. **Decisions due:** `python campaign/followup.py due`. For each item: `python campaign/learn.py report > /tmp/learning.txt`, then `create_session(source_url add-vee, title "add-vee follow-up: <Company> <key>", prompt = followup.py prompt <slug> <key> --learning /tmp/learning.txt, permission_mode "auto", tags ["add-vee-followup", "company:<slug>"])`, then `followup.py start <slug> <key> --session <id>`.
   **Every tick, after step 5: strategist results.** `python campaign/followup.py pending`. For each, `get_session`; when it's idle/completed, fetch its branch and read `output/<slug>/followups/<step>/decision.json`:
      - `send`: run `narrative_check.py` on its `email.md` (must be clean, and `decision.json` → `checks` must show the reviewer's approval); then create the Gmail draft. V/N/T/L: **a reply in the same thread** (`create_draft` with `replyToMessageId` = the thread's `last_message_id`, to the same person, subject "Re: <original>"), images inline as for email 1. C: a new email to the new person (to gefen@etico.cr if their address isn't verified, as for email 1). Copy the folder to `companies/<slug>/followups/<step>/`. `followup.py decided <slug> <key> --decision send --type <T> --draft-id <id> --reason "<angle>"`. Notify: `<Company>: follow-up <type> ready in Gmail for <role>, send on <date>. <angle>`.
      - `wait` / `stop`: `followup.py decided … --decision wait --until <ISO>` or `--decision stop --reason …`; one line to the sponsor only for `stop`.
      - A failed check, or a session stale for 24 h: send it back once with the reason (`send_message`); after that, tell the sponsor in one line.
   d. **The daily SEO-jobs route** (SCOUT.md → Daily SEO-jobs route): `create_session(source_url "https://github.com/gefenhermesh/add-vee-runs", title "add-vee jobs scout <date>", prompt "You are the daily jobs scout: follow campaign/SCOUT.md → Daily SEO-jobs route.", permission_mode "auto", tags ["add-vee-jobs"])`. When it reports back, `git pull`; **post the day's `campaign/scout/seeker/<date>.md` to the sponsor in full** (his own job list, the one message he asked for daily, sponsor 2026-11-24; the exception to one-line notices). If it reports a proposal, also notify the sponsor in one line: `SEO jobs: <Company> is hiring <role> (<link>). Reply "release <slug>"`. Released job-route companies start before anything else (`priority`).
   e. **LinkedIn posts reminder (sponsor, 2026-11-25).** Right after posting the job list, send the sponsor one more line: `LinkedIn posts search: when your computer is on, open Claude there and say "run the LinkedIn posts search" (steps: campaign/scout/LINKEDIN_POSTS.md).` LinkedIn's post search needs his logged-in account, so it runs on his computer, never in a cloud session. When its results file `campaign/scout/linkedin_posts/<date>.md` lands on main, post it to him in full like the job list. One reminder a day; don't repeat it on later ticks.
   **Once a week (Sunday's first tick after 09:00 US Eastern):** `learn.py report` (one line to the sponsor if something changed). Then **start the scout as its own session**: `create_session(source_url "https://github.com/gefenhermesh/add-vee-runs", title "add-vee scout <date>", prompt "You are the weekly scout: follow campaign/SCOUT.md → Running the scout.", permission_mode "auto")`. When it reports back, merge its branch into main (`git fetch origin <scout branch> && git merge --no-edit origin/<scout branch>`, then `propose.py check`, push), and pass its one line to the sponsor. When the sponsor writes "release a, b" here, set those companies to `queued`.
7. Write `/tmp/results.json` (each action plus `"ok"`, plus `session_id` / `draft_id` where relevant, plus `error` if it failed). Run `python campaign/tick.py apply /tmp/results.json`, then commit and push.
8. Reply: the notification lines first, then one line per other action. Nothing else.

## Never
- Never paste company material (research, findings, drafts, coverage) into this chat. One-line status and links only; this session must stay small.
- Never send email or contact anyone. Drafts only; the sponsor sends.
- Never start a company that isn't `queued`. The sponsor releases companies (`held`/`proposed` → `queued`).
- Never do a company's audit work in the manager session.
