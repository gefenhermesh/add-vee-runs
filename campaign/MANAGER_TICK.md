# The hourly campaign manager tick

The scheduled task fires this every hour in a **fresh, short session** with this repo. Its job is to look, act, record and leave. It does no audit work. All decisions come from `campaign/tick.py`, so a quiet hour costs almost nothing.

## Steps
0. **Repos:** if `add-vee-runs` isn't in this session, attach it with `add_repo` (owner `gefenhermesh`, repo `add-vee-runs`, access `push`), clone it, and work from it. The tick needs no other repo.
1. `git pull`, then `python campaign/tick.py sessions`. That prints the company session ids to check.
2. For each id, call `get_session(session_id)`. Write `{ "<id>": {"status_bucket": ..., "status": ...}, ... }` to `/tmp/sessions.json`, using the scratchpad if there is one.
3. `python campaign/tick.py plan /tmp/sessions.json`. That prints a JSON list of actions. **If it's empty, stop here:** reply only "No changes." and don't notify.
4. Carry out each action, in order:
   - `start`: `create_session` with `source_url`, `title` and `prompt` from the action. Use permission mode `auto`, never `plan`. Record the new `session_id`.
   - `nudge`: `send_message` to `session_id` with `message`.
   - `notify`: send `message` as a phone notification (`PushNotification` if available), and put it first in your final reply.
   - `mark`: nothing to call. `apply` records it.
5. Write the results (each action plus `"ok": true/false`, `session_id` for starts, `error` if it failed) to `/tmp/results.json`, then `python campaign/tick.py apply /tmp/results.json`.
6. Commit and push `campaign/state.json` and `campaign/log.md`.
6b. **Replies and sends (once a day, first tick after 08:00 Israel time):** follow LEARNING.md → The loop, step 2: log newly sent email-1 threads, detect and classify replies, and record them with `learn.py`. **Notify the sponsor immediately for any human reply.** Commit `campaign/learning/`.
6c. **Weekly (Sunday's first tick):** `learn.py report`, then the scout's proposals and `learn.py pick` (LEARNING.md → step 3). Notify the sponsor that the week's picks are ready to release.
7. Final reply: the notification lines first (if any), then one line per other action. Nothing else.

## Never
- Never send email, create drafts or do any company's work here. Company sessions do that.
- Never change `tick.py`'s decisions by hand. If something looks wrong, notify the sponsor instead.
- Never start a company that isn't `queued` in `state.json`. The sponsor or the weekly scout queues companies.
