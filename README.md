# add-vee-runs

The private store for the add-vee prospecting campaign. It's the shared notebook between the **campaign manager** (an hourly, short-lived session) and the **company sessions** (one per company, each running the full add-vee audit). The design is in the add-vee repo: `docs/proposals/2026-11-12-prospecting-loop.md` and `docs/proposals/2026-11-12-outreach-methodology.md`.

**Audit data does not live here.** Since 2026-11-12, add-vee commits each company's full `output/<slug>/` to that company session's own working branch in the add-vee repo (`scripts/save_output.py`, after every step). That's what lets a run resume after a usage limit on a fresh machine. This repo holds only the **campaign**: the company list, the pitch, and each company's outreach.

```
campaign/
  pitch.md       the sponsor's own pitch: the fixed base of every email (sponsor-owned; the system never edits it)
  state.json     one record per prospect: stage, company session id, attempts, ask track, cohort
  log.md         the manager's tick log + the weekly cohort learning log
companies/
  <slug>/
    run_summary.json      all the campaign manager reads about a run, incl. the add-vee branch that holds its output
    company_profile.json  situation, finding pattern, emphasis
    highlights.json       the angle, lead CONFIRMED findings, Action Plan sections to show
    outreach_brief.json   opener (+ source), chosen findings, team recommendations, ask track, rationale
    outreach/             email drafts + screenshots, and the Action Plan PDF
```

Rules
- **Nothing is ever sent automatically.** The campaign manager and company sessions only create Gmail drafts. The sponsor reviews, approves and sends every email personally.
- Every number in an email traces to a reviewer-CONFIRMED claim in that company's checkpointed `claims_ledger.json`.
- Audit outputs stay in add-vee (on the company's branch). Only the files above are copied here.
