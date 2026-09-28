# parsec v4 -- G arm: global-scope, shared-bundle hill-climb (G2)

**Spec:** `docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` (branch `parsec-v4-docs`), §2
**Agent model:** `claude-sonnet-4-6`
**Optimizer model:** `claude-opus-5` (`optimizer_skill: claude-code`, `algorithm_skill: hill-climb`)
**Budget (actual, per `state.json`):** `max_iterations: 15, stall: 6, max_usd: 1000.0,
max_optimizer_usd: 400.0, stop_at_reward: 1.0` -- the vendored recipe's `capevolve.yaml` shows
different values (a post-run edit); see
[`../../../recipes/v4/v4_g_e1/README.md`](../../../recipes/v4/v4_g_e1/README.md).
**Ledger:** [`results.json`](results.json) (hand-assembled from the run's `events.jsonl`/`state.json`
-- no generator script exists yet)
**Heatmap:** [`../../../ui/heatmap_v4_g_e1.html`](../../../ui/heatmap_v4_g_e1.html)
**Recipes:** [`../../../recipes/v4/v4_g_e1/`](../../../recipes/v4/v4_g_e1/)
**Artifacts:** [`../../../artifacts/v4/v4_g_e1/`](../../../artifacts/v4/v4_g_e1/) (`best/` = `cand_0004`,
`rejected/cand_{0001,0002,0003,0005,0006}/`)
**Per-task reports:** [`../../../reports/task-by-task/v4/v4_g_e1/`](../../../reports/task-by-task/v4/v4_g_e1/)
(`<task>.md`, 34 files -- generated auto+diff blocks only, no hand-written narrative yet)
**Cost/time source:** [`cost_time/`](cost_time/) (`v4_g2_e1_results_table.md`)
**Run dirs:** `run_baseline_fix_20260925_003926` (baseline), `run_optimize_fix_20260925_082813`
(optimize loop), both under
`.../parsec_g2/.capevolve/v4_g2_e1/` in the `parsec_g2` worktree.
**T vs. G:** see [`../comparison.md`](../comparison.md)

## The one-line result

Unlike T2 (one optimizer loop per task), G2 evolves **one shared bundle across all 34 tasks at
once**: every iteration is a full 170-rollout sweep (34 tasks x 5 trials) scoring the same candidate
bundle everywhere, and the optimizer edits that one bundle based on the aggregate signal. After 6
iterations the run stopped (see "Data-quality caveats" -- not a clean budget stop) at `cand_0004`
(`best_id`), raising the all-tasks mean reward from 0.8488 (our own zero-shot baseline) to 0.9434
(+0.0946), for roughly **$418.79 and 50.5h** of optimizer+eval time (before the metering-gap floor
adjustment below) -- **cand_0006**, a later *rejected* candidate, actually scored higher on
aggregate (0.9521) but failed the accept test against its parent `cand_0004` (paired delta not
resolvable at that sample size); `best_id` tracks the best-so-far *accepted* candidate, not the
best-ever-scored one.

## Aggregate: our baseline vs. each iteration

| tranche | n | our baseline (mean) | seed | cand_0001 | cand_0002 | cand_0003 | cand_0004 (best_id) | cand_0005 | cand_0006 | Δ best_id vs baseline |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| all | 34 | 0.8488 | 0.8488 | 0.9274 | 0.9353 | 0.9109 | **0.9434** | 0.9376 | 0.9521 | +0.0946 |
| regression | 30 | 0.8573 | 0.8573 | 0.9399 | 0.9428 | 0.9191 | **0.9441** | 0.9457 | 0.9551 | +0.0868 |
| challenge | 4 | 0.7852 | 0.7852 | 0.8339 | 0.8791 | 0.8498 | **0.9381** | 0.8774 | 0.9296 | +0.1529 |

`seed` is `our_baseline` reused unchanged (`baseline_reused` event) -- G2 doesn't re-measure it. All
figures above are validation-split, `n=5` trials/task, matching T2's convention. There is no
`FINAL`/held-out-test number: the one `FINAL` eval this run started never completed (see caveats).

`results.json`'s `best` column (task-wise oracle: the *max* over seed/cand_0001-6 for each
individual task, `best_tag` varying per task) averages higher still --0.9672 all-tasks-- than any
single candidate's own mean above, `cand_0004` included. That oracle number is not something a
single shared bundle can actually achieve in one shot (it would require picking a different
candidate per task, which defeats the point of a shared bundle); read it as an upper bound on how
much headroom the 6 candidates collectively found, not as a result G2 delivers.

## Coverage: no per-task targeting, by design

G2 has no analogue to T2's "21 of 34 tasks" coverage table -- every iteration scores all 34 tasks,
every time, because the bundle is shared. There's no equivalent of T4's regression check either: G2
never merges independently-optimized pieces, so there's nothing to check for merge-induced
regressions. The relevant per-task question for G2 is simply "did the accepted candidate's own edits
help or hurt *this* task" -- visible in the heatmap's per-task rows, not summarized here.

## Cost + wall clock

Source: [`cost_time/v4_g2_e1_results_table.md`](cost_time/v4_g2_e1_results_table.md).

| | eval cost | eval time | optimizer cost | optimizer time | total cost | total time |
|---|--:|--:|--:|--:|--:|--:|
| baseline (reused, not re-run here) | $0.00\* | 23,003.55s (6.4h) | -- | -- | $0.00\* | 23,003.55s (6.4h) |
| 6 scored iterations (cand_0001-6) | $105.35\* | 129,800.77s (36.1h) | $313.45 | 51,863.34s (14.4h) | $418.79\* | 181,664.11s (50.5h) |
| **grand total** | **$105.35\*** | **152,804.32s (42.4h)** | **$313.45** | **51,863.34s (14.4h)** | **$418.79\*** | **204,667.66s (56.9h)** |

\*Floor, not the true figure -- see caveat 1 below.

**The optimizer dominates cost here too, more than in T2:** ~75% of the $418.79 total (excluding
baseline) is the optimizer proposing the next shared-bundle edit, vs. T2's ~85%/15% split -- similar
shape, though G2's per-iteration eval is far more expensive per call ($0-29/call across 170 rollouts
at once) than T2's per-task eval, simply because every iteration touches all 34 tasks instead of one.

## Comparing G to T

See [`../comparison.md`](../comparison.md) for the full T-vs-G head-to-head (cost, wall time,
reward lift by tranche, and what a clean comparison still needs) -- it isn't repeated here since it
belongs to neither arm alone.

## Data-quality caveats

1. **Runner `cost_usd`/`tokens` show as exactly `0.0`/`0`** for the baseline/seed eval and for
   `cand_0001` and `cand_0002`'s evals -- a metering/instrumentation gap in this harness version, not
   a true zero cost. `cand_0003` onward logs substantial nonzero cost/tokens (~$25-29,
   ~7.5-9M tokens) for the same 170-rollout eval size, and `runner_seconds` is nonzero and in the same
   range for every row including the zero-cost ones. Every eval-cost figure above is a **floor**,
   undercounting by roughly 3 evals' worth (~$75-85 at the cand_0003-0006 rate) -- do not read
   "$418.79" or "$105.35" as exact.
2. **The run stopped after `cand_0006` without an obvious budget trigger.** `state.json`'s `stall: 2`
   (of a `stall: 6` budget) and `iterations: 6` with `max_optimizer_usd: 400` not yet spent ($313.45)
   suggest an interruption, not a designed stop. `events.jsonl` confirms this: it shows an
   `eval_start` for a 7th candidate (`cand_0007`) with no matching `evaluate`/`step`, and the
   optimizer's cumulative cost/tokens/time in `state.json` exceed the sum of the six logged `step`
   events by almost exactly one more optimizer call's worth (~$71, ~213K tokens, ~3.5h) -- i.e. the
   optimizer proposed a 7th candidate, that candidate's eval sweep started, then the process stopped.
   See `cost_time/v4_g2_e1_results_table.md`'s footnotes for the exact arithmetic. Whether this was a
   deliberate stop (matching T2's per-task "good enough" cutoff) or an infrastructure interruption
   (as affected three T2 tasks, per [`../v4_t_e1/summary.md`](../v4_t_e1/summary.md)) is not yet
   confirmed.
3. **The one `FINAL` (held-out test-split) eval never completed.** `events.jsonl` shows a single
   `eval_start` on `split=test`, `tag=FINAL` (right after `cand_0003`'s step) with no matching
   `evaluate` -- consistent with `splits.json`'s `test_used: false`. `events.jsonl` shows the run's
   process was restarted twice while resuming from state (three separate `run_config`/
   `target_profile` pairs across the two run dirs); this FINAL attempt fell in one of those restart
   gaps. All reward figures in this document are validation-split, not held-out test.
4. `results.json`'s `best`/`best_tag`/`best_n` columns are a **per-task oracle** (max over
   seed/cand_0001-6 for each task individually) built for the heatmap's per-task view -- they are not
   the same as `best_id_overall` (`cand_0004`, the actual best-so-far *accepted* single bundle). See
   "Aggregate" above for why these two numbers diverge.

## Next moves (open)

- **A. Confirm whether the run's stop after `cand_0006` was deliberate or an interruption** (caveat
  2) -- if infrastructure, consider resuming to let the optimizer either use more of its
  `max_optimizer_usd: 400` budget or hit `stall: 6` on its own.
- **B. Get the metering gap fixed** for future runs (caveat 1) so eval cost/tokens are accurate from
  `seed` onward, not just from `cand_0003`.
- **C. Run the `FINAL` held-out test-split eval to completion** for `cand_0004` (`best_id`), so G2 has
  a test-split number comparable to T2's `final`/test figures.

For what a clean T-vs-G comparison still needs, see [`../comparison.md`](../comparison.md).
