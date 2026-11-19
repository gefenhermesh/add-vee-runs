# Instructions for a campaign company session

You were started by the campaign manager to run **one company** end to end: the full add-vee audit, then the outreach draft. You are a normal add-vee session. Everything in add-vee's `CLAUDE.md` applies unchanged, including the Gate 1-2 stop and its depth. This file only adds the campaign parts.

**Never send email.** You create Gmail drafts only. The sponsor reviews, approves and sends every email personally.

## 1. Setup (first thing, and again after any restart)
1. add-vee is your working repo. Attach the campaign repo with `add_repo` (owner `gefenhermesh`, repo `add-vee-runs`, access `push`) and clone it to the folder next to add-vee (`../add-vee-runs`). If it's already there, `git -C ../add-vee-runs pull`.
2. Read `../add-vee-runs/campaign/state.json` (your company's entry), `../add-vee-runs/companies/<slug>/scout.json` if it exists, and `../add-vee-runs/campaign/pitch.md` §0-0c (the email rules).
3. Report: `python ../add-vee-runs/campaign/status.py <slug> loop_a --branch "$(git branch --show-current)"`.

## 2. Run the audit
Run it exactly as `CLAUDE.md` says for "run the audit for <domain>", including the tailoring step (`docs/pipeline/tailoring.md`) and `save_output.py` after every step (your output lives on this session's add-vee branch).

Report each milestone with `status.py` (one line each, with a short `--note`):

| When | Stage |
|---|---|
| Loop A starts | `loop_a` |
| Gate 1-2 presented, before you end the turn | `waiting_gate_1_2` (the manager then notifies the sponsor) |
| The sponsor approved in this session; Stage 3-4 starts | `loop_b` |
| Visibility Report published | `report` |
| Loop C starts | `loop_c` |
| Action Plan published, `highlights.json` written | `action_plan` |
| Outreach work starts | `outreach` |
| Gmail draft created | `done --draft-id <id>` |

## 3. Outreach (after the Action Plan)
1. **Contacts:** use `scout.json` if the scout found them. Otherwise research the right person (CEO at a small company, or the marketing lead) and their email (public sources first, then the company's address pattern). Record what's verified and what isn't in `companies/<slug>/scout.json`. You can't verify mailboxes from a cloud session; the sponsor verifies with Hunter.
2. **Brief:** write `companies/<slug>/outreach_brief.json` (shape: `companies/bay/outreach_brief.json`). Include situation, finding pattern, angle, lead CONFIRMED claim ids, the opener and its source, contacts, and a rationale paragraph for the sponsor.
3. **Email 1:** follow `pitch.md` §0, §0b and §0c exactly. Use the reference email `companies/bay/email_draft_v4.md` for shape and length (about 150 words, sponsor's voice, warm sourced opener, two images, soft "happy to send it over"). Every number is a CONFIRMED claim. Save the text as `companies/<slug>/email_draft_v1.md` with claim ids noted.
4. **Images:** from this company's Action Plan, the same way as for Bay. Serve `output/<slug>/` locally and screenshot it with Playwright at deviceScaleFactor 2:
   - image 1 is the whole "What the audit found" block;
   - image 2 is the content-plan heading (with the cluster/page counts) plus the first 3 clusters fading out, then the first 2 off-page moves fading out.

   Compress each to under ~180 KB and save them in `companies/<slug>/outreach/`.
5. **Gmail draft** (Gmail connector, which must be signed in as **gefen@etico.cr**, the sending address. If it's signed in as another account, don't draft there; report `outreach --note "gmail connector not on gefen@etico.cr"`): inline images, plain-text alternative. Address it to the contact **only if their email is verified**. Otherwise address it to the sponsor's own Gmail account (the account the connector is signed into) and say "address not verified" in the brief. Then `status.py <slug> done --draft-id <id>`.
6. Write `companies/<slug>/outreach_features.json` with every feature in `campaign/learn.py` FEATURES (the choices you made: recipient role, opener type, subject style, email variant, finding pattern, and so on). The manager logs it when the sponsor sends.
7. Commit and push everything in `add-vee-runs`.

If the Gmail connector isn't available in this session, stop at step 4, report `outreach` with `--note "gmail connector unavailable"`, and say so in your final message. The manager will tell the sponsor.

## 4. Resuming (after a usage limit, a restart or a manager "continue" message)
1. Redo Setup step 1. If `output/<slug>/` is missing or incomplete on this machine, check out your add-vee branch from the remote (the branch is in `status.json`). Everything was saved there by `save_output.py`.
2. `python scripts/run_ledger.py status <slug>` and continue from the recorded resume point.
3. If you're waiting for the sponsor at Gate 1-2, make sure `status.json` says `waiting_gate_1_2`, then stop.

## 5. Don't
- Don't send email, and don't edit `pitch.md` (the sponsor owns it).
- Don't skip or shorten any audit step to save time or usage. The sponsor chose quality over speed and cost.
- Don't start a second company. One session, one company.
