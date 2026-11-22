# Campaign log

The manager appends one line per tick. Cohort learning notes go under "## Cohorts".

## Ticks
- 2026-11-20T23:51:43+00:00 mark upwind done
- 2026-11-20T23:51:43+00:00 draft upwind
- 2026-11-20T23:51:43+00:00 notify upwind done
- 2026-11-20T22:55:22+00:00 mark gambit-security done
- 2026-11-20T22:55:22+00:00 draft gambit-security
- 2026-11-20T22:55:22+00:00 notify gambit-security done
- 2026-11-20T22:55:22+00:00 mark glow-io done
- 2026-11-20T22:55:22+00:00 draft glow-io
- 2026-11-20T22:55:22+00:00 notify glow-io done
- 2026-11-20T16:54:01+00:00 mark gambit-security running
- 2026-11-20T16:54:01+00:00 mark upwind running
- 2026-11-20T16:54:01+00:00 mark glow-io running
- 2026-11-20T06:54:09+00:00 mark glow-io waiting_gate
- 2026-11-20T06:54:09+00:00 notify glow-io gate
- 2026-11-20T05:54:24+00:00 mark upwind waiting_gate
- 2026-11-20T05:54:24+00:00 notify upwind gate
- 2026-11-20T05:54:24+00:00 start glow-io
- 2026-11-20T04:55:09+00:00 mark vega-security done
- 2026-11-20T04:55:09+00:00 draft vega-security
- 2026-11-20T04:55:09+00:00 notify vega-security done
- 2026-11-20T04:55:09+00:00 start upwind
- 2026-11-20T00:54:24+00:00 nudge vega-security
- 2026-11-19T21:54:21+00:00 mark vega-security running
- 2026-11-19T21:54:21+00:00 mark gambit-security waiting_gate
- 2026-11-19T21:54:21+00:00 notify gambit-security gate
- 2026-11-19T20:54:34+00:00 mark vega-security waiting_gate
- 2026-11-19T20:54:34+00:00 notify vega-security gate
- 2026-11-19T20:54:34+00:00 start gambit-security
- 2026-11-19T19:46:19+00:00 start vega-security
- 2026-11-19T19:53:00+00:00 manager set up (session_01FkmvpNPQPiaJcrqHcmBq7V, trigger trig_01TYro24KNGAHSNPwqrdkfJM hourly :53); first tick: vega-security loop_a, no actions; daily check: no prospect email-1 sent yet, no replies
- 2026-11-19T20:58:00+00:00 sponsor approved vega-security Gate 1-2 in the manager session ("move on with vega"); relayed to its session
- 2026-11-19T21:31:00+00:00 vega-security gate_1_2_approval.json written on campaign/vega-security (099a80b) from the sponsor's "move on with vega"; Vega session told to merge master and follow the new section
- 2026-11-20T07:54:00+00:00 daily check: no prospect email-1 sent yet, no replies
- 2026-11-20T16:25:00+00:00 sponsor asked to verify Vega review-profile facts: PeerSpot 0 reviews holds; G2 'Vega' = web scanner holds (G2 blocks fetches, checked via Google). Recorded in companies/vega-security/live_checks.json. Live-check gate pushed to add-vee branch system/live-check-gate (not merged)
- 2026-11-20T16:37:00+00:00 sponsor approved Gate 1-2 for gambit-security, upwind, glow-io ("approve all pending loop a"); approval files pushed to their branches, sessions messaged
- 2026-11-20T17:06:38+00:00 followup: vega-security/1 email1 sent to CMO
- 2026-11-20T20:10:00+00:00 sponsor: merge #13 (stuck-job detection, ~100-question target) and use Gemini for stuck AI Mode; rule merged as add-vee #14; Gambit, Upwind, glow.io told to merge master and switch
- 2026-11-20T20:45:00+00:00 sponsor: Bright Data credits at 0, pause all Bright Data use until payment resumes. Gambit, Upwind, glow.io told to continue without it or stop at paused_brightdata; no new starts; scout caps 0. add-vee #15 merged.
- 2026-11-21T05:10:00+00:00 sponsor: pause the campaign until Bright Data resumes; hourly tick disabled; add-vee #17 merged.
- 2026-11-22T21:55:07+00:00 followup: bay/1 email1 sent to CEO
- 2026-11-22 Bay email 1 sent to yuval@bay.io (sponsor's explicit request; v5, etico images, 'a unique research system'); follow-up thread bay/1, learn.py logged (features reconstructed).
- 2026-11-22 sponsor: drafts must carry the Gmail signature. Gambit, glow.io, Upwind drafts recreated with includeSignature (sponsor's edited text kept) and the old ones deleted; rule added to MANAGER_TICK and state.rules. add-vee #20 merged.

## Cohorts

## 2026-11-19 · Scout run 1
Long list: 130 companies (Firgun 13 Nov, Telegram marketing jobs, Avi Lewis list). Filter: `campaign/scout/filter_2026-11-19.md`. Recon: 12. Proposed 10 (plurai, buildots, darrow, scaleops, zenzap, capitolis, bites, daylight-security, edelbyte, dreeze). Held: geoedge (exception without funding; watch for new VP Marketing), dealhub (blocked: SEO Lead). Picks (learn.py, no outcome data yet): capitolis, plurai, scaleops (exploit), buildots, zenzap (explore). LinkedIn People-tab checks for the sponsor are in each `companies/<slug>/scout.json` → `linkedin_checks_for_sponsor`.
