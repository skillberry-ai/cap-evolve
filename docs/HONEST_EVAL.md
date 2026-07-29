# Honest evaluation in cap-evolve

cap-evolve's one differentiator is that its numbers mean something. Optimizing a
prompt/skill/tool against a metric is trivially gameable — you can hill-climb on
the same data you report. The substrate (`cap_evolve`) makes that hard *by
construction*, and the rules below are enforced in code, not just documented.

## The four guarantees

1. **Seeded, frozen splits — and big enough to gate on.** `make_splits(task_ids,
   seed, ratios)` partitions tasks deterministically. The split is written to the
   run dir once (`splits.json`) and every skill reads it back — no skill re-splits
   or peeks. `check_val_size` (run at split freeze *and* at `baseline`) **refuses**
   a val split with 0 or 1 tasks (`TinyValSplitError`): with n=1 the paired delta
   has 0 degrees of freedom, so the gate could only degenerate to "any Δ>0 wins".
   Below 5 val tasks the run proceeds but logs a `split_warning`, and each gate
   decision is flagged `LOW CONFIDENCE`. `CAPEVOLVE_ALLOW_TINY_VAL=1` opts out —
   and means you accept a non-honest gate.

2. **The test set is sealed.** `RunDir.consume_test()` flips a `test_used` flag
   and raises `TestSealError` on any second access. The held-out number is
   produced exactly once, at `finalize`. (See `splits.py`, `rundir.py`.)

3. **Acceptance is gated on val, with significance.** `gate.decide(...)` refuses
   any split but `val` (`TrainGateError`) and, by default, accepts a candidate
   only when the improvement exceeds `k · SE` — so noise is not mistaken for
   progress (`mode="significant"`). Other modes (`strict`, `threshold`,
   `simplicity_tiebreak`) exist but never relax the val-only rule. The gate reads
   only the **primary** metric (the scalar `reward`); any shown-only secondary
   metrics a scorer emits (`Score.metrics`) are for display and cannot move the
   decision. In `mode="paired"` (the default when per-task data exists) `k` is a
   *z* multiplier, but SE(Δ) is estimated from the same n val deltas — so the bar
   uses the equivalent **Student-t** multiplier at df = n−1 (`stats.t_critical`).
   t ≥ z always, so the correction only ever makes the gate *stricter*: at n=3 the
   bar widens 1.32×, at n=10 1.06×, at n=30 1.02×, converging to `k · SE`.

4. **Variance is measured, not assumed.** With `num_trials > 1`, each task gets a
   mean and stderr; `combined_stderr` mixes between-task and within-task error;
   `pass_k` reports the probability all k i.i.d. trials succeed (tau-bench style).

## Why no central engine?

prior agent-optimization work proved the design with a six-axis engine. cap-evolve keeps the *discipline*
but moves the orchestration into skills, so the pipeline runs on any host with no
framework lock-in. The discipline can't drift because the only place rewards are
aggregated, splits are made, the gate is applied, and test is sealed is
`cap_evolve` — every algorithm skill calls it and physically cannot gate on
train or re-score test.

## What this costs you

Honest eval needs enough tasks to split three ways and (ideally) multiple trials.
For tiny task sets, expect wide error bars and a conservative gate that rejects
marginal edits — that is the point.

## Sources
- prior agent-optimization work: `gates.py` (`val_improvement_significant`), `eval/base.py` (combined_stderr, pass^k), `splits.py`.
- tau2-bench: pass^k and reward-on-correct-action evaluation.
