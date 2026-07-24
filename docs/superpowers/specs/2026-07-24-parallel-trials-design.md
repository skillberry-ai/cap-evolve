# Parallel multi-trial evaluation — Design

**Date:** 2026-07-24
**Status:** Approved design, pre-implementation
**Branch:** `feat/parallel-trials`

## Goal

Default **`num_trials = 10`** for all benchmarks and both tiers (smoke + full), and make
those trials **run in parallel** (concurrency 10) rather than sequentially.

## Why it's not just a config knob

The harness (`harness._run_and_score`) only parallelizes trials if the adapter implements
**`run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [rollout_t0, …]}`**; otherwise it
loops `for k in range(n_trials)` **sequentially**. The CI template adapters
(`templates/adapters/{tau2_bench,swe_bench,skillsbench}`) did **not** implement it, and CI uses a
single-task split — so 10 trials would run serially and the existing concurrency knobs
(`TAU2_MAX_CONCURRENCY`, `SWEBENCH_MAX_WORKERS`, `SKILLSBENCH_CONCURRENCY`), which parallelize
*tasks within a trial*, had nothing to parallelize.

## Design

### Shared helper (core) — tested once
`core/cap_evolve/trials.py::run_trials_pool(run_one, tasks, *, n_trials, base_seed, max_workers)`
runs the whole `task × trial` grid concurrently over the adapter's existing `run_target`,
returning trial-ordered `{task_id: [rollout_t0, …]}`. Trial `k` uses `seed = base_seed + k`
(independent draws). Exceptions become error rollouts; `max_workers=1` runs sequentially with an
identical result. Exported from `cap_evolve`.

### Thin `run_trials` in each template adapter (delegate to the helper)
- **tau2** — pool bound = `TAU2_MAX_CONCURRENCY`.
- **swebench** — pool bound = `SWEBENCH_MAX_WORKERS`. Parallelizes patch **generation** only;
  the harness still scores (Docker eval) each rollout sequentially in `_persist_trial`.
- **skillsbench** — pool bound = `SKILLSBENCH_CONCURRENCY`. Concurrent `bench eval run`
  subprocesses stay isolated by the per-seed jobs dir + a unique temp skills dir.

No change to the base `CapabilityAdapter` → **no blast radius** for other adapters/users; the 3
CI adapters opt in.

### Config (`ci/benchmarks/lib/run_task.sh`)
- `num_trials: 1 → 10` (applies to baseline, optimize val, and finalize test evals; all benches,
  both tiers — `run_task.sh` has no tier branching).
- Export **`TAU2_MAX_CONCURRENCY=10`**, **`SWEBENCH_MAX_WORKERS=10`**, **`SKILLSBENCH_CONCURRENCY=10`**
  (exported so they reach `os.environ`, matching the existing `export SKILLSBENCH_MODEL` pattern for
  import-time reads).

## Known follow-up (flagged, NOT in this PR)

Existing frozen baselines — the 6 smoke tasks and the tau2 **full** baselines being frozen now —
were captured at **`num_trials=1`**. With eval at 10 trials, base→opt comparisons mix a 1-trial
baseline mean with a 10-trial candidate mean (no baseline variance estimate). For a fully honest
comparison the baselines should be **re-frozen at `num_trials=10`** on the runner (`freeze_baseline`
picks up the new `num_trials`). Deferred per the chosen scope ("Full: config + run_trials + conc=10",
not "+ re-freeze").

## Testing
- `run_trials_pool` unit tests (shape, per-trial seed order, concurrent==sequential, exception →
  error rollout, zero trials).
- Adapters compile; `run_task.sh` lints; `num_trials: 10` + the three exports present.
- Functional (real models / Docker) verification happens on the next benchmark run on skillberry-1.
