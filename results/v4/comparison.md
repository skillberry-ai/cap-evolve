# parsec v4 — T vs. G

**T:** [`v4_t_e1/summary.md`](v4_t_e1/summary.md) (task-by-task hill-climb)
**G:** [`v4_g_e1/summary.md`](v4_g_e1/summary.md) (global-scope, shared-bundle hill-climb, `v4_g2_e1`)

This is the only home for numbers that compare the two arms directly. Neither arm's own summary
carries a cross-arm table — read each arm's `summary.md` for what it did on its own, and this file
for how the two stack up.

## Held constant / what differs

Held constant across both arms: the same 34 tasks (4 categories), the same shared seed bundle
(`artifacts/v4/seed/`, byte-identical between the two runs), the same `our_baseline` zero-shot
measurement as the pre-optimization reference point, and the same two models — `claude-sonnet-4-6`
as the target/agent model, `claude-opus-5` (via `optimizer_skill: claude-code`,
`algorithm_skill: hill-climb`) as the optimizer. Both also share the no-holdout split discipline
(`train == val == test`), just at different scales — one task at a time for T, all 34 at once for G.

What differs:

- **Scope per optimizer call.** T2 edits one task's bundle at a time using that task's own signal;
  G2 edits one shared bundle using the aggregate signal across all 34 tasks at once, every iteration
  a full 170-rollout sweep (34 tasks × 5 trials).
- **Budget.** T2's per-task budget: `num_trials: 5, max_iterations: 3, stall: 2, max_usd: 50.0,
  max_optimizer_usd: 20.0`. G2's actual run budget (per `state.json`, not the post-run-edited
  `capevolve.yaml` — see [`v4_g_e1/README.md`](v4_g_e1/README.md) for that divergence):
  `max_iterations: 15, stall: 6, max_usd: 1000.0, max_optimizer_usd: 400.0, stop_at_reward: 1.0`.
- **`gate_k_se`.** G2 ran with `gate_k_se: 0.0` — any positive paired delta is accepted, ignoring
  the SE margin. T2 has no analogous setting; it doesn't gate on paired significance at all.

## Cost, time, and reward lift

| | T2 (task-by-task) | G2 (global, shared bundle) |
|---|--:|--:|
| tasks touched per iteration | 1 | 34 (all) |
| tasks covered overall | 21 of 34 (13 already at ceiling, skipped) | 34 of 34, every iteration |
| iterations run | 98 rows across 21 tasks (up to 3 accepted rounds/task) | 6 (stopped, see G's caveat 2) |
| total cost | $437.24 | $418.79 (floor — see caveat below) |
| total wall time | 140,868s (39.1h) | 181,664s (50.5h) |
| optimizer share of cost | ~85% ($373.03) | ~75% ($313.45) |
| reward lift (regression tranche) | +0.119 (0.845 → 0.963, T1 seed vs T2 final, 30 tasks) | +0.087 (0.857 → 0.944, our_baseline vs cand_0004, 30 tasks) |
| reward lift (challenge tranche) | +0.081 (0.792 → 0.873, 4 tasks) | +0.153 (0.785 → 0.938, 4 tasks) |

Reading this side by side: **similar total spend, G2 took ~30% longer wall-clock and delivered a
smaller lift on the regression tranche but a larger lift on the challenge tranche** than T2 — though
neither comparison is apples-to-apples yet. T2's "reward lift" mixes 21 optimized tasks with 13
already-perfect ones held at their seed score (see `v4_t_e1/summary.md`'s own footnote on this);
G2's lift is a genuine 34-task mean since every task is scored every iteration. T2 also got cut off
by design (stopped optimizing tasks once they were "good enough" per-task), while G2 was cut off by
an apparent interruption (`v4_g_e1/summary.md`'s caveat 2) with `max_optimizer_usd=400` not yet
reached ($313.45 spent) — so G2's numbers above are a mid-flight snapshot of an unfinished run, not
a completed budget, in a way T2's aren't.

## Cost shape: the optimizer dominates in both arms

In both arms, the optimizer proposing candidates costs far more than the runner scoring them —
~85% of T2's total ($373 of $437), ~75% of G2's ($313 of $419, itself a floor). The per-call rate
tells the same story: T2's optimizer calls run roughly 90-130× the cost of an eval call on the same
task; G2's per-iteration eval ($0-29/call across 170 rollouts at once) is far more expensive in
absolute terms than a single T2 eval, simply because every G2 iteration touches all 34 tasks instead
of one, but the optimizer-vs-eval ratio still lands in the same range as T2's.

G2's own eval-cost figures are additionally undercounted by a metering/instrumentation gap (runner
`cost_usd`/`tokens` read as exactly `0.0`/`0` for `baseline/seed`, `cand_0001`, and `cand_0002`) —
see [`v4_g_e1/summary.md`](v4_g_e1/summary.md)'s caveat 1 and
[`v4_g_e1/cost_time/v4_g2_e1_results_table.md`](v4_g_e1/cost_time/v4_g2_e1_results_table.md)'s
footnote. Tracked in issue
[skillberry-ai/cap-evolve#562](https://github.com/skillberry-ai/cap-evolve/issues/562).

## What a clean comparison still needs

- A completed, non-interrupted G2 run — either more iterations from where it stopped, or a
  deliberate stop at a designed budget boundary, so its numbers aren't a mid-flight snapshot.
- The `FINAL` held-out test-split eval run to completion for G2's `best_id` (`cand_0004`), so G2 has
  a test-split number comparable to T2's `final`/test figures — right now every G2 number above is
  validation-split only.
- The metering gap (issue #562) fixed, so G2's eval cost/tokens are exact from `seed` onward instead
  of a floor.
- Optionally, a matched-iteration-count cut of T2's data, since T2's 21-task, up-to-3-round
  optimization isn't naturally the same "amount of optimization" as G2's 6 iterations over all 34
  tasks — this table is a first look, not the final word on which scope is more efficient.
