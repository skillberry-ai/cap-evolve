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
   any split but `val` (`TrainGateError`) and, by default, accepts a candidate
   only when the improvement exceeds `k · SE` — so noise is not mistaken for
   progress. The default mode in a real run is **`paired`** (see [Gate
   modes](#gate-modes)); no mode relaxes the val-only rule. The gate reads
   only the **primary** metric (the scalar `reward`); any shown-only secondary
   metrics a scorer emits (`Score.metrics`) are for display and cannot move the
   decision.

4. **Variance is measured, not assumed.** With `num_trials > 1`, each task gets a
   mean and stderr; `combined_stderr` mixes between-task and within-task error;
   `pass_k` reports the probability all k i.i.d. trials succeed (tau-bench style).

## Gate modes

Set with `gate_mode` in `capevolve.yaml` (strictness with `gate_k_se`, default
`1.0`). All five live in `core/cap_evolve/gate.py` `decide()`; all are val-only.

| `gate_mode` | rule | when to use |
|---|---|---|
| **`paired`** — **the default** | accept iff `mean(per-task Δ) > k_se · SE(Δ)`, where `Δ[t] = cand[t] − curr[t]` over the same val tasks | default and recommended: candidate and current are scored on the *same* tasks, so cross-task variance cancels and the test is far more powerful than `significant` |
| `significant` | accept iff `Δ(means) > k_se · sqrt(SE_cand² + SE_curr²)` | when the two sides were *not* scored on the same tasks. Less powerful — it pays for cross-task variance that the paired test cancels |
| `threshold` | accept iff `Δ > threshold` (flat margin) | you have a domain minimum worthwhile gain ("don't bother unless +2pp") |
| `strict` | accept iff `Δ > 0` | only with a near-zero-variance scorer (deterministic, single correct answer) |
| `simplicity_tiebreak` | `Δ > 0` accepts; on a near-tie (`abs(Δ) ≤ 1e-9`) accept the *smaller* candidate (`candidate_size < current_size`) | Occam bias against edits that bloat without earning it |

**`paired` is what actually runs by default.** `templates/project/capevolve.yaml`
ships `gate_mode: paired`, and the harness sets `mode="paired"` itself whenever the
caller pinned no mode and per-task val data aligns (`harness.py`
`_gate_and_record`, `gepa.py` `_full_val_gate`). The algorithm skills'
`--gate-mode auto` means exactly "let the engine pick paired".

Note the one asymmetry: `gate.decide()`'s own `mode=` parameter still defaults to
`"significant"`, because a bare caller passing only two means and two SEs has no
per-task data to pair. `paired` also falls back to `significant` when
`paired_deltas` is empty.

### Why `paired` banks single-task gains

Under `paired`, the SE comes from the *spread between tasks' deltas*, not from
per-trial noise — so it is non-zero even at `num_trials=1`. A candidate that fixes
one task out of `n` and breaks nothing gets `Δ̄ = 1/n` and `SE = 1/n` exactly, so at
the default `k_se=1.0` it just misses the strict `Δ̄ > k·SE` bar, while at the
`gate_k_se: 0.2` the examples use it accepts. Under `significant` at
`num_trials=1`, both SEs come from the between-task spread of the *absolute* scores
(`combined_stderr`), which is much larger — a one-task gain on 10 tasks faces a
`0.233·k` bar instead of `0.100·k`.

### Small-sample caveat (current behavior)

The bar is a fixed `k · SE`, with no t-correction and no minimum-val-size guard, so
it is optimistic on tiny val splits. Two degenerate cases are handled loudly, never
silently:

- **`SE = 0`** (`paired` with `n=1`, or every task moved identically; `significant`
  with a zero combined SE, typically `num_trials=1`) — the gate logs a
  `gate_warning` event and applies a documented **strict fallback** (accept any
  `Δ > 0`). The decision `reason` says `SE=0 → STRICT fallback, warned`.
- **no paired data** — `paired` falls back to `significant` rather than passing.

Fix: raise `num_trials` and use a val split big enough that between-task spread is
meaningful.

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
