# Honest evaluation in cap-evolve

cap-evolve's one differentiator is that its numbers mean something. Optimizing a
prompt/skill/tool against a metric is trivially gameable — you can hill-climb on
the same data you report. The substrate (`cap_evolve`) makes that hard *by
construction*, and the rules below are enforced in code, not just documented.

## The four guarantees

1. **Seeded, frozen splits — and big enough to gate on.** `make_splits(task_ids,
   seed, ratios)` partitions tasks deterministically. The split is written to the
   run dir once (`splits.json`) and every skill reads it back — no skill re-splits
   or peeks. `check_val_size` **refuses** a val split with 0 or 1 tasks
   (`TinyValSplitError`): with n=1 the paired delta has 0 degrees of freedom, so the
   gate could only degenerate to "any Δ>0 wins". It runs at every point a run commits
   to a val split — split freeze, `baseline`, `reuse_baseline`, `--resume` — **and
   `gate.decide` itself refuses fewer than 2 matched pairs**, which is the chokepoint
   no caller can route around: a copied or hand-written `splits.json`, or a healthy
   split whose *realized* pair count collapsed because a candidate errored on most val
   tasks, is caught there. Below 5 val tasks the run proceeds but logs a
   `split_warning`, each gate decision is flagged `LOW CONFIDENCE`, and `report.md`
   leads with a low-confidence banner.

   `CAPEVOLVE_ALLOW_TINY_VAL=1` opts out — and means you accept a non-honest gate.
   Such a run is **permanently branded**: a `tiny_val_bypass` marker is written to
   `state.json`, `final.json` carries `honest_gate: false` plus a `warnings` array,
   `report.md` leads with `⚠ NOT AN HONEST GATE` and retracts its "held-out tasks the
   optimizer never saw" claim, and the dashboard renders a red banner above every
   number. The bypass does not travel across runs: `reuse_baseline` re-checks the
   copied split, so a bypassed run cannot become an unmarked seed for a later one.

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
   decision. In `mode="paired"` (the default when per-task data exists) SE(Δ) is
   estimated from the same n val deltas, so the standardized mean difference is
   t-distributed, not normal. `k_se` is therefore consumed as a **z quantile**: it is
   converted to its one-sided normal tail α = P(Z > k_se), and the realized bar is
   `t_{1−α, df=n−1} · SE`. t ≥ z is a theorem for every finite df, so the correction
   only ever makes the gate *stricter*, and the widening depends on both `k_se` and n:

   | `k_se` | α | ratio at n=3 | n=7 | n=10 | n=30 |
   |---|---|---|---|---|---|
   | 0.2 | 0.4207 | 1.135× | 1.044× | 1.029× | 1.009× |
   | 1.0 | 0.1587 | 1.321× | 1.091× | 1.059× | 1.018× |
   | 3.0 | 0.0013 | 6.402× | 1.635× | 1.365× | 1.093× |

   **Two caveats, stated plainly.** (a) This is a *change in the meaning of `k_se`* —
   before, it was the multiplier itself. See `CHANGELOG.md`; previously-accepted
   candidates near the old bar can now be rejected. (b) The correction does **not**
   apply on the SE=0 path: when every val delta is identical (common with a binary
   scorer that flips the same task set) the paired SE collapses, and the gate takes the
   documented, loudly-warned STRICT fallback — accept on Δ̄ > 0 with no bar — at any n.
   `k_se` above 3 is unnecessary and above 26.5 raises: its normal tail underflows
   float64, and returning an uncorrected z bar instead would be silently wrong.

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
