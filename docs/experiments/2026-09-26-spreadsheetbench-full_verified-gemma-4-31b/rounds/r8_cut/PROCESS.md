# PROCESS — round 8 (`r8_cut`), explainability

Iteration: `r8_cut` (round 8), parent/champion `r3_decide` (val 0.8875). Gate: full val (n=40
paired), paired, `k_se 1.0`, `--gate-against control` with 2 concurrent replicates, concurrency 8,
1 trial. **Outcome: REJECTED on the gate** (`verdict_stable: true` under both replicates → a reject,
not an inconclusive).

## Provenance of this file — read this first

The driver session that BUILT and EVALUATED this candidate died on an `api_error` after its val
evaluation completed and before it booked anything (`events.jsonl` `host` record:
`terminal_reason: api_error`, `returncode: 1`, `num_turns: 341`). This file was written by the
retry driver. The `PROCESS.md` found in the working copy was `r2_numeric`'s, carried forward
unmodified — so it is **replaced** here rather than amended, and nothing above the candidate's diff
is inherited from it.

What survived the crash and is therefore the basis of every claim below: the candidate diff, the 120
val rollouts (`r8_cut`, `ctl_null_i7`, `ctl_null_i7r1`), and the round table `work/round_i7.json`.
What did not survive: the original driver's diagnosis and stated intent. **The edit is therefore
reconstructed from its diff, and its rationale is stated as reconstruction, not as recovered
intent.** No rollout was re-run; the round was already paid for.

## The candidate — what the diff actually is

A **pure deletion**, one file, one hunk:

- `task_template.md`, READ section: removed ~134 words (1362 → 1228) covering (a) `ws[a1].value`
  returns formula TEXT / the computed number lives in the `data_only` copy / never save the
  `data_only` workbook, and (b) print the distinct `(repr, type)` of a filter column, compare both
  sides via `str(a).strip().lower()`, and `''` is a present empty value rather than a failed lookup.
- `prompt.md`: **byte-identical to `r3_decide`** (verified by `diff`). Every rule deleted above still
  exists there verbatim (lines 40-65). All 7 load-bearing placeholders intact.

So this is not a new rule and not a behavioural change — it is a **de-duplication** of text that
appeared in both files the agent reads first.

## Cluster targeted, and why it was a defensible round

| cluster | tasks | tag | root cause | lever |
| --- | --- | --- | --- | --- |
| CONFLICT/BLOAT — the same rule stated twice across `prompt.md` and `task_template.md` | not a failing-task cluster | CONSOLIDATION | r7_path's measured RESULT: its rule FIRED on 39/40 rollouts and still cost `353-29` and `36097`, i.e. words added to these two files displace reading/scoping work | delete duplicated text (the one deletion the guidance permits: text shown to be redundant) |

The hypothesis was the direct converse of r7's finding: if adding words costs attention, removing 134
words that carry no unique information should buy it back for free. That is a real hypothesis about a
real measured effect, and a deletion is the only round in this run that could test it.

## VERIFY-THE-FIX / blast radius — what the measurement said

**Gate.** `r8_cut` **0.8750** vs concurrent controls **0.8718** / **0.8947**. `gate_delta 0.0`
(threshold `0.0367`); against the stored parent Δ̄ `-0.0125` (threshold `0.0379`).
`verdict: reject` under BOTH replicates. Round noise: `parent_vs_gate_ref_drift -0.0157`,
`null_delta_between_control_replicates 0.0229`, `noise_floor_from_control 0.0256`.

**Per-task vs BOTH controls, with the measurement audited before crediting anything:**

- Naive table: fixed `[56427]`, broke `[53647]`.
- **`56427` is NOT a fix.** Both controls scored 0 there on
  `sandbox exec failed: 500 Server Error ... Infrastructure error, not a prompt defect; do not
  optimize against it`. The candidate's 1.0 is an environment artifact. Credited as **no fix**.
- **`53647` IS a causal break**, 1.0 → 0.0 against both controls. Grader: *"2 cell(s) hold a number
  HIGHER than expected. TYPE: 1 cell(s) hold int where float was expected — match the expected type
  exactly."* That is the formula-vs-value and native-type failure mode the deleted text addresses,
  verbatim. Its target range `E7:E16` is filled with `'=IF(C8>1,E31,...)'` formulas whose `data_only`
  value is `None` — the hardest case in val for precisely the two deleted rules. Attenuation, not
  loss: `data_only` appears **13** times in the candidate's trace vs **16** in the control's, and the
  control's trace runs 35.6k chars to the candidate's 31.2k, finishing on an explicit reconcile
  (*"The reconciliation for E7 (8.75) and E8 (10.0) is perfect"*) the candidate never reaches.
- Corrected reading: **0 genuine fixes, 1 genuine break, Δ 0.0.** Blast-radius class of the edit was
  judged BOUNDED (deletion of duplicated text) and the measurement shows it was in fact **UNBOUNDED**
  — the duplication was load-bearing.

**The transferable finding.** For this reader (`gemma-4-31B-it`, strong-but-not-frontier),
duplication between `prompt.md` and `task_template.md` is **reinforcement, not redundancy**, and it
is load-bearing exactly on the tasks where a rule is hardest to apply. The rule surviving "one file
away" sufficed for 39 of 40 val tasks and failed on the one that most needed it. **Do not
de-duplicate a rule out of `task_template.md` on the grounds that `prompt.md` still states it.**

## Decision

Booked `--decision reject --reject-basis gate`. `verdict_stable: true` with `gate_delta 0.0` means
growth cannot rescue a zero delta, so `inconclusive` would misreport it — the round did judge this
edit, and it refuted it. Champion unchanged: `r3_decide`, val 0.8875.

## Deliberately skipped

- Any further candidate: this was round 8 of `max_iterations: 8`. `spend.py` read `narrow_scope`
  (88% consumed) before this booking and `stop` after it.
- `341-40` (openpyxl load→save float re-serialization vs the grader's `round(x,2)`, confirmed at
  sheet-XML level) and the intermittent sandbox 500s (`56427` here) — environment/serialization,
  not prompt-space, per the arm instructions' environment-fault rule.
- Editing the adapter, grader, harness, benchmark or environment — out of bounds throughout.
- Re-testing any hypothesis a prior RESULT refuted (r2 sentinel-meaning, r4 cells-written-as-progress,
  r5 self-computed VERDICT, r6/r7 CHANGED-vs-N_RESPONSIBLE, r7 base-rate-blind sizing) — and, from
  this round on, prose de-duplication on this surface.
