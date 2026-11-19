# The learning loop: lift the reply rate

**The goal (sponsor, 2026-11-19):** the measure of success is the **reply rate**. Learn which companies, situations, contacts and emails get replies, do more of what works, and keep testing new things. In the long run, find the ideal company profile: the companies most likely to want to work with the sponsor. Don't get stuck on cybersecurity. Prefer B2B tech, but go for variety, because variety is how the system learns.

## What's recorded (memory)
- `learning/outreach_log.jsonl`: one record per email-1 thread, written **when the sponsor actually sends it** (the system never sends). Each record holds:
  - the slug, `sent_at` and `gmail_thread_id`;
  - **features**: the company, situation, contact and email choices (`learn.py` → `FEATURES`: industry, stage, situation, size, geo, marketing gating, trigger, finding pattern, recipient role, ask track, opener type, email variant, subject style, send slot, contact verified);
  - follow-ups;
  - the **outcome**.
- `learning/learnings.md`: the current evidence, rebuilt by `python campaign/learn.py report`.
- `learning/hypotheses.md`: what we're testing and why, and what we concluded. One line each, dated.

## Outcomes
`positive` (wants the report, a call, or to talk work) · `neutral` (a polite "not now", or a referral) · `negative` ("not interested", "stop") · `auto` (out of office: wait) · `none` (14 days after the last touch with no reply). **The reply rate counts positive + neutral + negative.** The positive rate is tracked too. Report requests and meetings are flagged separately.

## The loop
1. **Company session, when the draft is ready:** write `companies/<slug>/outreach_features.json` with every feature (all choices it made).
2. **Daily (manager tick):** in gefen@etico.cr, find newly **sent** email-1 threads (Sent, to the contact, matching the draft's subject). For each new one, `learn.py add` (features + thread id). Then check every open thread for a **reply** from the company. Classify it, record it with `learn.py outcome`, and **notify the sponsor immediately for any human reply**: that's the moment that matters. If a classification is unclear, ask the sponsor instead of guessing.
3. **Weekly (Sunday):** run `learn.py report`, update `hypotheses.md`, then let the scout propose candidates with their features, and choose the week's companies with `learn.py pick <candidates.json> <n>`:
   - about **60% exploit**: candidates whose features have the best sampled reply rates;
   - about **40% explore**: candidates with feature values tried fewer than 3 times (a new industry, stage, trigger or recipient role).

   The sponsor sees the picks with their reasons and releases them.

## How to learn at small numbers (honesty)
- A few emails a week means noisy rates. Every rate comes with its 80% range. **Don't change course on one reply.** A conclusion needs a range that clearly separates from the rest, or the same direction holding across several weeks.
- **Change few things at a time** in the email itself (subject, opener, images), so a difference can be traced to its cause. Company mix can vary more, since every company is a different draw anyway.
- Leading signals worth noting before replies accumulate: report requests, how quickly people reply, replies from a second person at the company (forwarding).
- Write what was learned into `hypotheses.md` and, once it's solid, into the scout's scoring (SCOUT.md) or the pitch rules (pitch.md, which the sponsor owns: propose the change, don't make it).

## Starting mix (week 1, before any data)
Variety on purpose:
- industries: security, devtools, data/AI infrastructure, fintech, HR/martech;
- stages: seed to Series C;
- situations: just launched to established;
- recipient roles: CEO and marketing leader.

The sponsor's held picks (Vega, Gambit, Upwind, glow.io) go first, with features recorded like everything else.
