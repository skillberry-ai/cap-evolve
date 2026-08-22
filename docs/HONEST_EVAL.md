# Honest evaluation in cap-evolve

cap-evolve's one differentiator is that its numbers mean something. Optimizing a
prompt/skill/tool against a metric is trivially gameable — you can hill-climb on
the same data you report. The substrate (`cap_evolve`) makes that hard *by
construction*, and the rules below are enforced in code, not just documented.

## The four guarantees

1. **Seeded, frozen splits.** `make_splits(task_ids, seed, ratios)` partitions
   tasks deterministically. The split is written to the run dir once
   (`splits.json`) and every skill reads it back — no skill re-splits or peeks.

2. **The test set is sealed.** `RunDir.consume_test()` flips a `test_used` flag
   and raises `TestSealError` on any second access. The held-out number is
   produced exactly once, at `finalize`. (See `splits.py`, `rundir.py`.)

3. **Acceptance is gated on val, with significance.** `gate.decide(...)` refuses
   any split but `val` (`TrainGateError`) and accepts a candidate only when the
   improvement exceeds `k · SE`. The bar is `Δ > k·SE` and not `Δ > 0` because
   search is a noise amplifier: screen enough candidates and the best-looking one
   is best by *luck*, so a `Δ > 0` rule banks noise and the val curve climbs while
   nothing actually improved. Clearing `k` standard errors of the measurement's own
   error is what makes an accept mean something — which is why turning the gate
   down to `strict` on a stochastic scorer quietly invalidates the whole run.

   **Gate modes** (`gate_mode` in `capevolve.yaml`, `gate_k_se` sets `k`):

   | mode | rule | when |
   |---|---|---|
   | `paired` | mean(per-task Δ) > `k`·SE(Δ) over the **same** val tasks | **the default** — every run takes it when per-task data exists; cross-task difficulty cancels, so it is strictly more powerful |
   | `significant` | Δ > `k`·√(SE_cand² + SE_curr²) | unpaired fallback — only correct when the two sides were *not* scored on the same tasks |
   | `threshold` | Δ > `T` | you have a domain minimum worth banking |
   | `strict` | Δ > 0 | only a near-zero-variance (deterministic) scorer |

   Any other value raises. `decide()`'s own `mode=` parameter defaults to
   `significant` purely as the bare-caller fallback; the loop overrides it to
   `paired` (`harness.py:1524-1526`, `gepa.py:741-743`) and the shipped template
   sets `gate_mode: paired`. No mode relaxes the val-only rule. The gate reads
   only the **primary** metric (the scalar `reward`); any shown-only secondary
   metrics a scorer emits (`Score.metrics`) are for display and cannot move the
   decision.

4. **Variance is measured, not assumed.** With `num_trials > 1`, each task gets a
   mean and stderr; `combined_stderr` mixes between-task and within-task error;
   `pass_k` reports the probability all k i.i.d. trials succeed (tau-bench style).
   A `k` greater than the trial count is **undefined, not zero**: `aggregate_scores`
   omits it from `pass_k` / `pass_at_k` entirely (so the default `num_trials: 1`
   emits only `{"1": ...}`), `stats.pass_k` returns `None` rather than a plausible
   `0.0` for such a `k`, and no surface renders a `k` it did not measure — human
   surfaces (`report.md`, the dashboard KPI strip) list exactly the measured ks, and
   the JSON surfaces simply omit the key. Reporting `pass^2 = 0.0` on a single-trial
   run would read as "0% reliable" when it only means "not enough trials"; inventing
   a `pass^2 = N/A` on a run where `ks` never included 2 is the same defect mirrored.

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
