# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

<!-- cap-evolve:insights-append-below -->

## epic-decompose pipeline mechanics (trace-confirmed, iteration 1)
- What worked (confirmed by trace analysis of all 8 val rollouts, cand_0001/seed; gate RESULT pending):
  - Phase machine: DECOMPOSE → REVIEW_DECOMP → REVISE_DECOMP (first revision UNCONDITIONAL — runs even when the review passes) → RE_REVIEW_CHECK → (if revised) RE_REVIEW → REVISE_CHECK → BATCH_DONE ("review passed or cycle cap reached"). Consequence: defects the FIRST review lists always get a revise pass; defects only the RE-review finds are never fixed. Enforcement should therefore target the first review + the decomposer, not the loop thresholds.
  - The external scorer tolerates unfixed OBSERVATION minors (015/016/018/020 pass 5/5 with minors like "bundling is defensible", "signal arguable") but docks for artifact DEFECTS (019's spec/content boundary overlap → 4/5 "solid with one minor overlap"). The discriminating fix is defect-class elimination, not "fix all minors" (which would churn passing tasks).
  - All 7 passing tasks' docs-authoring epics already satisfy the Jira-priority derivation (Critical→P0, Major→P1, else P2); only 019-E004 deviated — the derivation rule is a safe mechanical guard.
- What didn't (confirmed by trace):
  - Prose rules alone get skipped: the docs-priority derivation rule existed verbatim in decompose Step 4 and the decomposer still copied the HLR label. The first review also missed the boundary overlap that the re-review caught — semantic review of this defect class is stochastic in GLM-5.3; it needed the mechanical check.
- Promising but not yet tried: gate_failure_impact/gated_by completeness as a script check (fires on 020's pre-revision state — needs the decompose-time-vs-revise-time fix-path equivalence verified first).

