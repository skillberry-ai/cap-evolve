# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## epic-decompose pipeline mechanics (trace-confirmed, iteration 1)
- What worked (confirmed by trace analysis of all 8 val rollouts, cand_0001/seed; gate RESULT pending):
  - Phase machine: DECOMPOSE → REVIEW_DECOMP → REVISE_DECOMP (first revision UNCONDITIONAL — runs even when the review passes) → RE_REVIEW_CHECK → (if revised) RE_REVIEW → REVISE_CHECK → BATCH_DONE ("review passed or cycle cap reached"). Consequence: defects the FIRST review lists always get a revise pass; defects only the RE-review finds are never fixed. Enforcement should therefore target the first review + the decomposer, not the loop thresholds.
  - The external scorer tolerates unfixed OBSERVATION minors (015/016/018/020 pass 5/5 with minors like "bundling is defensible", "signal arguable") but docks for artifact DEFECTS (019's spec/content boundary overlap → 4/5 "solid with one minor overlap"). The discriminating fix is defect-class elimination, not "fix all minors" (which would churn passing tasks).
  - All 7 passing tasks' docs-authoring epics already satisfy the Jira-priority derivation (Critical→P0, Major→P1, else P2); only 019-E004 deviated — the derivation rule is a safe mechanical guard.
- What didn't (confirmed by trace):
  - Prose rules alone get skipped: the docs-priority derivation rule existed verbatim in decompose Step 4 and the decomposer still copied the HLR label. The first review also missed the boundary overlap that the re-review caught — semantic review of this defect class is stochastic in GLM-5.3; it needed the mechanical check.
- Promising but not yet tried: gate_failure_impact/gated_by completeness as a script check (fires on 020's pre-revision state — needs the decompose-time-vs-revise-time fix-path equivalence verified first).

<!-- cap-evolve:insights-append-below -->

## case-019 defect cluster (confirmed by cand_0001's RESULT)
- What worked (confirmed by RESULT, cand_0001): the diagnosis — the scored deduction is the spec-epic/content-epic boundary overlap (E001 "reference example of a correctly packaged tutorial" vs E003's authoring surface) plus the E002 gating-AC gap. The gate FIXED case-019 with edits targeting exactly these; the rejection was blast radius, not aim. The docs-priority minor (E004 P2) is NOT a scored deduction — the external scorer's visible feedback explicitly accepts P2 under the docs-exemption rule.
- What didn't (confirmed by RESULT, cand_0001): the enforcement chain — a 4-family script whose findings were folded into the FIRST review (driving the unconditional revision), a hard 8c exit-0 gate, and a broad must-fix enumeration — broke 013/014/016. Verification against FINAL artifacts is insufficient: the pipeline's states that matter (post-decompose, what the 8c check and the reviewer see) differ from final on every task whose reviser changed anything (014/017/018/020 in this seed's traces).
- Promising but not yet tried (shipped this iteration, cand_0002, RESULT pending): enforcement at the PRODUCER only — narrow two-check script, fail-open, wired at decompose 8c; reviewer gets pattern-naming (no script); reviser gets recipes keyed to the two defect classes.

## verification method (this iteration's addition)
- Per-file version histories reconstructed from ALL Write/Edit tool calls in the rollout stdout make "does the guard fire on any passing task?" a measurement over the exact states the guard sees, not an assertion about final artifacts. Cheap (~6 turns for 8 tasks) and it is the difference between cand_0001's SAFE claim and its measured regression.
- Review-issue extraction from every `decomp-review.md` frontmatter write in the stdout gives the first-review vs re-review issue lists — the ground truth for "would this recipe/rubric change fire on a passing task?" (No passing task ever listed an overlap- or gating-class issue in either review.)

