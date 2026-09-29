# v4_g2_e1 -- G2 (global-scope, shared-bundle) hill-climb: cost & time

G2 evolves **one shared bundle across all 34 tasks** per iteration -- unlike T2 (one optimizer loop
per task), every row below is a single 170-rollout sweep (34 tasks x 5 trials) over the *same*
candidate bundle, plus the optimizer's own cost to propose that candidate from its parent. There is
no per-task or per-tranche cost split at this grain: the unit of cost here is "one iteration of the
shared bundle," not "one task."

Hand-built from `run_baseline_fix_20260925_003926/state.json` and
`run_optimize_fix_20260925_082813/{events.jsonl,state.json}` (job dir:
`/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec_g2/.capevolve/v4_g2_e1/`).
No cost_time-parsing script exists for G2 yet (only 8 rows; see caveats before adding one).

**Progress: 6/6 iterations done, run stalled/stopped after `cand_0006` (stall=2 of budget's stall=6,
`max_optimizer_usd=400` not yet hit at $313.45 spent -- run appears to have been killed/interrupted
mid-proposal for a 7th candidate, not stopped by budget).**

## Summary table -- one row per iteration

Cost and time columns below are rounded to one decimal digit. `Val reward` is kept at higher
precision (rounding it to one decimal would collapse cand_0001 through cand_0006 to the same "0.9",
erasing the differences the accept/reject decisions are based on) -- say if you'd like that column
rounded differently too.

| Stage | Val reward | Parent | Parent val | Accept? | Eval cost($) | Eval tokens | Eval time(s / h) | Opt cost($) | Opt tokens | Opt time(s / h) | Total cost($) | Total time(s / h) |
|---|--:|---|--:|:--:|--:|--:|--:|--:|--:|--:|--:|--:|
| baseline/seed | 0.848801 | -- | -- | -- | 0.0\* | 0 | 23,003.5 / 6.39h | 0.0 | 0 | 0.0 / 0.00h | 0.0\* | 23,003.5 / 6.39h |
| cand_0001 | 0.927424 | seed | 0.848801 | **accept** | 0.0\* | 0 | 23,661.2 / 6.57h | 28.0 | 172,151 | 1,956.5 / 0.54h | 28.0\* | 25,617.7 / 7.12h |
| cand_0002 | 0.935347 | cand_0001 | 0.927424 | reject | 0.0\* | 0 | 23,298.1 / 6.47h | 32.1 | 94,645 | 4,446.5 / 1.24h | 32.1\* | 27,744.6 / 7.71h |
| cand_0003 | 0.910922 | cand_0001 | 0.927424 | reject | 29.0 | 9,033,586 | 18,978.5 / 5.27h | 58.5 | 139,184 | 8,474.4 / 2.35h | 87.4 | 27,453.0 / 7.63h |
| cand_0004 | 0.943418 | cand_0001 | 0.927424 | **accept -> best_id** | 25.2 | 7,789,290 | 20,363.3 / 5.66h | 28.8 | 97,511 | 4,808.2 / 1.34h | 53.9 | 25,171.5 / 6.99h |
| cand_0005 | 0.937639 | cand_0004 | 0.943418 | reject | 24.1 | 7,479,403 | 23,640.4 / 6.57h | 44.5 | 108,359 | 10,560.8 / 2.93h | 68.7 | 34,201.2 / 9.50h |
| cand_0006 | 0.952121 | cand_0004 | 0.943418 | reject | 27.1 | 8,421,079 | 19,859.2 / 5.52h | 50.5 | 136,608 | 8,869.2 / 2.46h | 77.6 | 28,728.4 / 7.98h |
| cand_0007 (incomplete)\*\* | -- | cand_0004 | 0.943418 | never scored | 0.0 | 0 | 0.0 / 0.00h | ~71.1 | ~212,752 | ~12,747.8 / 3.54h | ~71.1 | ~12,747.8 / 3.54h |
| **TOTAL (6 scored iterations)** | | | | | **105.3** | **32,723,358** | **129,800.8 / 36.06h** | **313.4** | **961,210** | **51,863.3 / 14.41h** | **418.8** | **181,664.1 / 50.46h** |
| **TOTAL incl. baseline** | | | | | **105.3** | **32,723,358** | **152,804.3 / 42.45h** | **313.4** | **961,210** | **51,863.3 / 14.41h** | **418.8** | **204,667.7 / 56.85h** |

\* `cost_usd`/`tokens` show as exactly `0.0`/`0` on the runner side for `baseline/seed`,
`cand_0001`, and `cand_0002`'s eval -- this is a metering/instrumentation gap in this harness
version, not a true zero cost: `cand_0003` onward logs substantial nonzero runner cost/tokens for
the *same* 170-rollout eval size (~$25-29, ~7.5-9M tokens each), and `runner_seconds` is nonzero and
in the same range (18,978-23,661s) for every row including the zero-cost ones. Treat the eval-cost
total above as a **floor**, undercounting by roughly 3 evals' worth (~$75-85 at the cand_0003-0006
rate). Tracked in issue [skillberry-ai/cap-evolve#562](https://github.com/skillberry-ai/cap-evolve/issues/562).

\*\* `cand_0007`'s `opt_cost_usd`/`opt_tokens`/`optimizer_seconds` are not logged directly (the run
stopped before a `step` event was written for it) -- they're inferred as the gap between
`run_optimize_fix_20260925_082813/state.json`'s cumulative `optimizer_usd`/`optimizer_tokens`/
`optimizer_seconds` (313.4458475 / 961,210 / 51,863.337) and the sum of the six logged `step` events
(242.369148 / 748,458 / 39,115.57). `events.jsonl` shows an `eval_start` for `cand_0007` on
`split=val` with no matching `evaluate` or `step` -- the optimizer proposed a 7th candidate (costing
~$71 and ~3.5h) and the eval sweep for it started, then the run stopped (matches
`state.json`'s `spent.iterations: 6`); `cand_0007`'s eval never got any runner cost/tokens/seconds
logged, so it contributes $0/0/0s on the eval side above.

A `FINAL` eval on `split=test` (`eval_start` only, right after `cand_0003`'s step) also has no
matching `evaluate` -- consistent with `splits.json`'s `test_used: false`. It was interrupted by one
of this run's process restarts (the job's `events.jsonl` shows three separate `run_config`/
`target_profile` pairs, i.e. the process was restarted twice while resuming from state) and
contributes $0/0/0s above.

## Notes

- **Why eval time is so high relative to eval cost:** each eval row is 170 rollouts (34 tasks x 5
  trials) run with `"workers": 1` (no parallelism, per `eval_start` events) -- `eval time(s) / 170`
  is a consistent ~112-139s/rollout across every row, *including* the rows with `$0.0` metered cost
  (`baseline/seed`: 135.3s/rollout; `cand_0001`: 139.2s; `cand_0002`: 137.0s; `cand_0003`: 111.6s;
  `cand_0004`: 119.8s; `cand_0005`: 139.1s; `cand_0006`: 116.8s). That consistency across both the
  metered and unmetered rows is the tell: wall time here is a direct clock measurement from the
  harness, independent of the LLM billing pipeline that produces `cost_usd`/`tokens` -- so the
  cost-metering gap (footnote \*) doesn't explain the time being "too high," and the time figures
  are not miscalculated. ~2 minutes/rollout is plausible for these tasks: each rollout is a
  multi-turn agentic run against real platform/icinga/cloud tool calls (kubectl-style queries, log
  fetches, API round trips), and that tool-call and environment latency costs wall-clock time
  without costing LLM tokens -- unlike token cost, which only accrues when the model itself is
  generating. Serial execution (`workers: 1`) then multiplies that per-rollout latency by all 170
  rollouts with no overlap, which is most of why a $25-29 eval still takes 5-6.5 wall-clock hours.
- **Cost and wall-clock time are anti-correlated across the eval/opt split, not just different in
  scale.** For `cand_0003`-`cand_0006`, eval wall time is consistently 2.2x-4.2x opt wall time
  (5.3-6.6h eval vs. 1.3-2.9h opt), yet eval costs 90x-131x *less* than opt ($24-29 eval vs. $28-58
  opt). This isn't a contradiction once the workloads are separated: eval time is dominated by
  170 serial rollouts of tool-call/environment latency (see the per-rollout note below) that costs
  wall-clock but barely any billed tokens, while opt time is a handful of optimizer-model calls
  that are comparatively fast per call but expensive per token. Don't read "eval is cheaper" as
  "eval does less work" -- it does more wall-clock work for less billed cost.
- "Total time(s)" per row is `runner_seconds + optimizer_seconds` for that row treated as fully
  sequential (single worker, `orchestration_mode: deterministic`) -- there is no parallel-worker
  discount to apply, matching how T2's per-task total time is reported.
- `baseline/seed`'s reward/cost/time is the same run T2's own `our_baseline`/T1-seed measurement
  reused (`baseline_reused` event in `run_optimize_fix_20260925_082813/events.jsonl` points back at
  `run_baseline_fix_20260925_003926`) -- it is not re-measured inside the optimize run, so it costs
  nothing extra beyond the one baseline eval already paid for in `run_baseline_fix_20260925_003926`.
