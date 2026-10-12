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

## case-019 defect cluster (confirmed by cand_0001's RESULT)
- What worked (confirmed by RESULT, cand_0001): the diagnosis — the scored deduction is the spec-epic/content-epic boundary overlap (E001 "reference example of a correctly packaged tutorial" vs E003's authoring surface) plus the E002 gating-AC gap. The gate FIXED case-019 with edits targeting exactly these; the rejection was blast radius, not aim. The docs-priority minor (E004 P2) is NOT a scored deduction — the external scorer's visible feedback explicitly accepts P2 under the docs-exemption rule.
- What didn't (confirmed by RESULT, cand_0001): the enforcement chain — a 4-family script whose findings were folded into the FIRST review (driving the unconditional revision), a hard 8c exit-0 gate, and a broad must-fix enumeration — broke 013/014/016. Verification against FINAL artifacts is insufficient: the pipeline's states that matter (post-decompose, what the 8c check and the reviewer see) differ from final on every task whose reviser changed anything (014/017/018/020 in this seed's traces).
- Promising but not yet tried (shipped this iteration, cand_0002, RESULT pending): enforcement at the PRODUCER only — narrow two-check script, fail-open, wired at decompose 8c; reviewer gets pattern-naming (no script); reviser gets recipes keyed to the two defect classes.

## verification method (this iteration's addition)
- Per-file version histories reconstructed from ALL Write/Edit tool calls in the rollout stdout make "does the guard fire on any passing task?" a measurement over the exact states the guard sees, not an assertion about final artifacts. Cheap (~6 turns for 8 tasks) and it is the difference between cand_0001's SAFE claim and its measured regression.
- Review-issue extraction from every `decomp-review.md` frontmatter write in the stdout gives the first-review vs re-review issue lists — the ground truth for "would this recipe/rubric change fire on a passing task?" (No passing task ever listed an overlap- or gating-class issue in either review.)

<!-- cap-evolve:insights-append-below -->

## The external judge's scoring mechanism (confirmed by cross-candidate rollout comparison, iterations 1-3)
- What worked (evidence: cand_0001 fixed 019 with a clean terminal review; cand_0002 fixed the overlap but left a NEW re-review minor — both directions observed):
  - The `decomposition_quality` judge (claude-opus-4-6, rubric in `epic-creator/eval/epic-decompose.yaml`: "4 = one minor gap (e.g. a soft AC, one under-justified edge)") reads the pipeline's FINAL adversarial review as part of its inputs and anchors on it. In all four observed 4/5s (seed-019, c2-019, c2-013, and by symmetry every flaky draw) the judge's cited gap = a defect-class minor unresolved in the terminal re-review; every observed 5/5 (c1-019, seed-013/014/017 clean; 015/016/018/020 observation-only) had none. The pipeline loop ends at `pass: true` (minors never fail a review), so any defect minor the first review misses, the reviser leaves, or the re-review newly finds is terminal.
  - The discriminator between docked and tolerated minors: **prescriptive vs hedged**. "Fix: state in E001's ACs…", "add the arrow to the diagram", "the field should follow the mandated derivation" → docked. "Defensible, but if…", "arguable either way", "no change required", "a human should confirm", "Confirm with the strategy author" → tolerated at 5/5.
  - The judge's feedback field is truncated at exactly 1288 chars; dims 1-2 are usually visible, the docking reason often is not. Reading the terminal review's issue list is the reliable proxy — it IS what the judge reads.
- What didn't (evidence: cand_0002 RESULT, broke 013):
  - Producer-side prevention of two defect classes was necessary but not sufficient — the re-review simply found a third class (parallel-supplier AC precision). The fix population must include the reviser (fix prescriptive minors, sweep adjacent instances of the fixed class) and the reviewer (don't escalate already-surfaced ambiguity), not only the decomposer.
  - Reviewer pattern-naming edits plausibly increased reviewer pedantry: c2-013's re-review listed 3 Completeness minors mirroring health warnings the seed run's reviewer (same artifacts shape) did not list. Reviewer edits should be NARROWING-only.
- Promising but not yet tried (shipped this iteration, cand_0003, RESULT pending): structural-only script enforcement (mermaid↔frontmatter/dangling/cycles — zero semantic judgment, so no false positives by construction) + the calibrated reviser discriminator + the Criterion-7 narrowing rule.

## Rollout-stdout reconstruction — the two parsing traps (method, iterations 2-3)
- Write-event-only reconstruction is WRONG for this pipeline: the decomposer writes bodies via Write and sets frontmatter via separate `frontmatter.py set` bash calls. Must replay both, in order. Two traps: (1) commands may chain several `frontmatter.py set` invocations (split on `frontmatter\.py"?\s+set` — cand_0001's agents quote it as `frontmatter.py" set` with a `$W` variable prefix); (2) snapshot the state at the FIRST review-file Write, not at any command containing `decompose_complete=true` (revisers grep for that string mid-revision, which yields transient partial states).
- The runtime layout for bundled scripts (confirmed from cand_0002's rollout): the candidate's `epic-decompose/` dir is staged at `skills/epic-decompose/epic-decompose/` under the case workspace cwd; the dual-path `CHECK=…` resolution pattern is proven to find it.

