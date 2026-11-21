# Follow-ups: how they're tracked, decided and written

Status: **approved by the sponsor 2026-11-20** ("approve and build it"); built the same day: `followup.py` (+ tests), add-vee `docs/campaign/followup-strategist.md`, `MANAGER_TICK.md` step 6. The pitch text (`pitch.md`) stays the sponsor's; wording below is suggested lines to adopt, not edits to it.

Builds on what's already decided: the negative rules and conditions in add-vee `docs/proposals/2026-11-12-outreach-methodology.md` §5, the sequence in `pitch.md` §3, and the learning loop in `LEARNING.md`.

---

## 1. The principle: every follow-up adds one new thing

A follow-up that repeats email 1 ("just bumping this") is the one that gets ignored. Each follow-up brings **one** thing the prospect hasn't seen:

| Type | The new thing | When it fits |
|---|---|---|
| **V. Full value** (the sponsor's "email 2") | What the full engagement is, and a deeper peek at the recommendations | Default first follow-up |
| **N. New evidence** | A fresh re-run of 2-3 of their prompts: what changed since email 1, or what's still wrong | Silence after V; or a finding that's likely to move |
| **T. Trigger** | Their own news (launch, round, hire, event, a competitor move) tied to a finding | Whenever a real trigger appears, any time in the sequence |
| **C. Committee** | Same findings, framed for a second person (CEO ↔ marketing leader, or the team that owns the fix) | After the first person's sequence is silent |
| **R. Reply handling** | An answer drafted for the sponsor: report request, objection, "not now", referral, out-of-office | Any reply. The sequence stops; the sponsor takes over |
| **L. Last check** | One short, polite close | End of a silent sequence. Never after a "no" |

So, to the question "more results or more pitch?": **both, in that order.** V gives the pitch (the full value) plus results they didn't see (the deeper recommendations). N gives results again, but new ones. Neither repeats email 1.

## 2. Content

### Email 1: small additions inside the existing format (sponsor, 2026-11-20)
A word here and there, not a rewrite. Suggested lines:
- In 2.1 (who I am): "…building **a unique research system** that uses AI agents…" (sponsor, 2026-11-21: always "unique research system")
- In the method line: "**People don't ask AI a keyword; they hold a conversation.** So I ran the real conversations Vega's buyers have…"
- Before the image: "…what would normally take **weeks of manual work**: 84 buyer questions, 252 conversations, every answer read."

### Follow-up V ("email 2"): the full value proposition
Same thread, day 4-6 business days. Structure:
1. One line back to email 1 (no "just following up"): "One thing I didn't get to in my last note: what a full engagement looks like."
2. **What the full engagement adds** (short bullets, the sponsor's list):
   - **More conversations, and more realistic ones**: the full buyer committee, every stage, with follow-ups.
   - **Your own context**: sales calls, objections and company materials, so the questions are the ones your buyers really ask.
   - **Every platform**: ChatGPT, Gemini, Google AI Mode, Perplexity, Copilot, Claude.
   - **A system you can question**: the team can ask the research's manager directly, dig into any result and keep learning from it.
   - **Run regularly**, so you see what moved and why.
   - **Help putting it in place**: SEO as the conductor (Idea B), working with product, PR, partners and sales.
3. **A deeper peek at the recommendations**: one CONFIRMED recommendation per owning team, 3-4 teams (the existing `{team_recos}`), plus the content-plan screenshot. Still not all the cards.
4. Idea C in one line: why this needs a person plus the system, not a tool alone.
5. CTA: "Happy to walk you and the team through it, 20 minutes."

### Follow-up N: new evidence
"I re-ran three of the questions this week. ChatGPT still says No to zero data retention; Google AI Mode now gets ingestion right." Built only from a fresh, logged run, reviewed like any claim, through the live-check gate. If nothing changed, say what still holds, in one line.

## 3. Who decides: the follow-up strategist (an agent), boxed in by rules, approved by the sponsor

Three layers, so the intelligence sits where it helps and can't do damage:

1. **Rules (deterministic, `followup.py`)**: what is never allowed (the six negative rules: no send without approval, stop on any reply, ≤2 follow-ups per person and ≤2 people per company, never two people the same day, CONFIRMED numbers only, verified addresses only) plus timing windows (business days in the recipient's time zone, not on their holidays). It decides **when a decision is due**, never what to say.
2. **The strategist (an agent, one short session per decision)**: when a decision is due, it reads the thread, the audit, the company's news since email 1 and what has worked for similar prospects (`learn.py`). It decides **whether, who, which type, which angle and when**, writes the draft, and records its reasoning and the evidence in `companies/<slug>/followups/<n>_decision.json`. It may decide to wait, or to stop.
3. **Checks, then the sponsor**: the reviewer (narrative mode) and the live-check gate on every fact; the manager creates the Gmail draft **as a reply in the same thread** and sends you one line: who, why, which type, send-on date. You approve, edit or kill it. Nothing is sent automatically.

## 4. Tracking

One record per contact thread, in `state.json` → `prospects[].threads[]`:
`contact · role · gmail_thread_id · email1_sent_at · step (sent → v_drafted → v_sent → n_sent → c_started → closed) · next_decision_at · last_signal · reply_class · followups[] (type, angle, decided_by, draft_id, sent_at)`.

What the daily check reads:
- **Sent mail**: detects the sponsor sending email 1 or a follow-up, and starts the clock.
- **Replies**: classified into positive, report request, objection, not now, referral, out-of-office, unsubscribe or bounce. Any human reply → push to the sponsor at once, sequence stops.
- **Out-of-office** → reschedule to the return date. **Bounce** → stop, mark the address, tell the sponsor.
- **Company news** (weekly, from the scout's sources): a trigger can pull a follow-up forward.
- Not tracked: opens (unreliable, and pixels hurt deliverability). If the report is ever sent as a link, views and new viewers become the strongest signal, per the methodology's condition table.

## 5. Learning
Every follow-up's features (type, angle, day, recipient role, images) go into `outreach_log.jsonl`, so `learn.py` can tell which follow-up types earn replies, and the strategist reads those results before deciding. The same honesty rules as `LEARNING.md` apply: at this volume, only patterns that hold over several weeks count.

## 6. What it takes to build (after approval)
- `campaign/followup.py`: thread state, the rules, `due` (which threads need a decision today). Tests like `test_tick.py`.
- `campaign/FOLLOWUP_STRATEGIST.md`: the strategist's instructions (inputs, the type menu, decision schema, writing rules from `pitch.md`).
- In add-vee: `scripts/rerun_prompts.py` for type N (a few prompts, logged, through the normal extraction and review).
- `MANAGER_TICK.md`: the daily step calls `followup.py due`, starts a strategist session per due thread, then drafts in-thread.
- `pitch.md`: the sponsor adds the follow-up V text in their own words (section 2.6).

## 7. Decisions for the sponsor
1. Approve the type menu and the order (V → N or T → C → L)?
2. The V bullets: right list and wording? Is "a system you can question" something you'll offer clients (a session they can talk to)?
3. Timing: V at 4-6 business days, N at about 10, committee at about 14, last check at about 21?
4. Email 1 additions in §2: adopt as written, or reword in your own words?
