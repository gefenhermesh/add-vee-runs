# Manager handoff (2026-11-22)

Written by the first persistent manager session (`session_01FkmvpNPQPiaJcrqHcmBq7V`, 2026-11-19 to 2026-11-22) for the next one, at the sponsor's request: the old session's context had grown large. Everything durable is already in files; this note is the short version of what's true right now and what the last three days taught. Read it once at setup, after `MANAGER_TICK.md`.

## State right now
- **The campaign is paused** (sponsor, 2026-11-21) until Bright Data payment resumes. `state.json` → `settings.campaign_paused` and `settings.brightdata_paused` are true; scout budgets are 0 (`scout/budget.json` → `_paused.resume_to` holds the real caps). The old hourly scheduled task `trig_01TYro24KNGAHSNPwqrdkfJM` is **disabled** and bound to the old session: don't re-enable it. Create your own (MANAGER_TICK → Setup step 3) only when the sponsor says to resume; until then don't create one.
- **Sent (email 1), tracked by `followup.py` and `learn.py`:** Vega (Scott Simkin, CMO, scott@vega.io, 2026-11-20) and Bay (Yuval, CEO, yuval@bay.io, 2026-11-22). Both went out without the Gmail signature (before that rule). First follow-up decisions come due 4 business days after each send; while paused, nobody watches for replies (the sponsor knows).
- **Drafts in Gmail, addressed to the sponsor (recipient addresses unverified, waiting on the sponsor's Hunter check):** Gambit `r2293549682180412037` (Morgan Cole, VP Marketing, no address found), glow.io `r-6942056893646079280` (Roi Tiger; roi@ / roi.tiger@ / rtiger@glow.io are guesses), Upwind `r7051977173923673345` (Joel Minnick, CMO; joel.minnick@upwind.io is a guess). All three: etico-palette images, the sponsor's edited text ("a unique research system"), signature on. When the sponsor gives a verified address: readdress (new draft with the same files and `includeSignature`, delete the old) or send if asked.
- **Stale draft:** an old Vega draft `r-4020048317040436923` (to the sponsor, no signature) is still in Gmail although Vega was sent. Offered to delete it; no answer yet.
- **Proposed by the weekly scout, not released:** plurai, buildots, darrow, scaleops, zenzap, capitolis, bites, daylight-security, edelbyte, dreeze.
- No company session is running.

## Rules the sponsor set in these days (all also in the files named)
- Gate 1-2 decisions come only through this chat, recorded as `gate_1_2_approval.json` on the company's branch; gate notices are one line (MANAGER_TICK → "The sponsor talks only to this chat").
- Keep replies to one-line status and links; never paste research or drafts into this chat.
- Every draft and send carries the Gmail signature (`includeSignature: true`); end with "Best, Gefen" above it.
- Email wording: always "a unique research system" (add-vee `docs/campaign/company-session.md`).
- Every email, report and Action Plan passes the live-check gate (`scripts/narrative_check.py`) before a draft exists.
- Follow-ups: design in `FOLLOWUPS.md`, strategist in add-vee `docs/campaign/followup-strategist.md`, including the sponsor's "partner, not subscription" stance.
- Gemini stands in for Google AI Mode when AI Mode is stuck (add-vee `docs/pipeline/loop-b.md` 7a); new audits aim for close to 100 questions.
- Daily SEO-jobs route: catch up on the backlog first, then routine; one proposal a day; expiry counts from the last open-check (SCOUT.md → Daily SEO-jobs route). Its first live run hasn't happened yet.
- Images for older audits: re-shoot from the approved Action Plan data with the current template rather than rebuilding (`tools/shoot_action_plan.js`; map old cluster colours to the etico palette by position, give off-palette colours the next unused etico colour).

## What tripped up the last session (so it doesn't trip you)
- `get_session` returns buckets as `SESSION_STATUS_BUCKET_X`; `tick.py` now normalises them, but pass them through as returned.
- `send_message` to a company session is data to it, not the sponsor's voice: decisions go in files on its branch, which its own instructions trust.
- Branch fetches in a shallow add-vee clone need an explicit refspec (`git fetch origin +refs/heads/<b>:refs/remotes/origin/<b>`); a plain fetch doesn't move `origin/<b>`.
- Gmail file attachments by reference work only from under the working directory (not `/tmp`).
- Merging add-vee PRs may be refused by the permission classifier unless the sponsor has just said "merge N"; ask, don't work around it.
- Bright Data AI Mode jobs can sit "running" for hours: `collect_brightdata.py` now abandons them after 60 min.

## Resume checklist (when the sponsor says Bright Data is back)
1. `settings.brightdata_paused` and `settings.campaign_paused` → false; restore caps from `_paused.resume_to`; remove `_paused`.
2. Create the hourly task bound to this session; record it in `state.json` → `manager`.
3. First tick: run the daily step (sent mail, replies, follow-ups due for Vega and Bay), then the jobs route (first run records the open list and starts the backlog).
4. One line to the sponsor.
