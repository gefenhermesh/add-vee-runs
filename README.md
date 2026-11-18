# add-vee-runs

The private store for the add-vee prospecting campaign. It's the shared notebook between the **campaign manager** (an hourly, short-lived session) and the **company sessions** (one per company, each running the full add-vee audit). The design is in the add-vee repo: `docs/proposals/2026-11-12-prospecting-loop.md` and `docs/proposals/2026-11-12-outreach-methodology.md`.

Company data lives here, and never in the add-vee tool repo (whose `output/*` stays out of git by design).

```
campaign/
  pitch.md       the sponsor's own pitch: the fixed base of every email (sponsor-owned; the system never edits it)
  state.json     one record per prospect: stage, company session id, attempts, ask track, cohort
  log.md         the manager's tick log + the weekly cohort learning log
companies/
  <slug>/
    checkpoints/ approved stage files, saved after every approved stage, used to resume on a fresh machine
    run_summary.json      all the campaign manager reads about a run
    company_profile.json  situation, finding pattern, emphasis
    highlights.json       the angle, lead CONFIRMED findings, Action Plan sections to show
    outreach_brief.json   opener (+ source), chosen findings, team recommendations, ask track, rationale
    outreach/             email drafts + screenshots, and the Action Plan PDF
```

Rules
- Nothing is sent from here. The manager creates Gmail drafts, and the sponsor approves and sends.
- Every number in an email traces to a reviewer-CONFIRMED claim in that company's checkpointed `claims_ledger.json`.
- Raw scrape data (`raw/`, extraction packets) stays out. Checkpoints hold approved stage outputs only.
