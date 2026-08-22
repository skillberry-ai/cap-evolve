---
name: baseline
description: Establish the starting point. Use after implement-and-check and before any algorithm. Creates the run directory, freezes the seeded train/val/test split (written once), scores the unmodified seed capability on val, and records it as the candidate every algorithm must beat. Reports the remaining headroom so a saturated seed stops the run before it spends budget.
component: phase
argument-hint: "--base .capevolve --project DIR --capability DIR [--seed N] [--ratios a,b,c] [--n-trials N] [--split-ids FILE] [--resume] [--reuse-baseline DIR]"
allowed-tools: Read, Write, Bash
provides: [splits, baseline, candidate, scores, traces]
needs: [project, tasks]
sources: []
---

# baseline — freeze splits, score the seed

baseline is the first phase that touches data, so it owns the run's one
irreversible decision: **the split**. It writes `splits.json` once (seeded), scores
the *unmodified* seed capability on val, and records that score as the bar every
algorithm must beat.

Run `implement-and-check` first. baseline re-runs that check itself and exits
non-zero before creating a run dir if it is red — a split frozen against a broken
adapter poisons every number measured afterwards.

## Why it matters
- **Fair comparison point.** Every algorithm hill-climbs *against* the baseline
  val score; a candidate that does not beat it is not progress.
- **Headroom.** The printed JSON carries `headroom` (`1 - val`) and
  `headroom_verdict`: `saturated` means the seed is already at the ceiling and
  further iterations buy noise — stop; `floor` (val at 0) usually means a
  mis-wired adapter rather than a hard task — re-check before spending budget;
  `ok` means proceed. The same verdict is logged as a `headroom` event so the
  orchestrator can stop on it with no human reading the number.

## Splitting choices
- **Seeded ratio split** (default `0.5 / 0.25 / 0.25`): deterministic given
  `--seed`. Reproducible runs partition identically.
- **Pinned split** (`--split-ids`): a JSON `{train,val,test}` of ids — use a
  benchmark's official split, or set all three equal to fit the whole set with
  **no holdout** (the test number is then a *fit* metric, not a held-out result;
  the run dir records a `splits_warning` saying so).
- A ratio split that leaves val or test empty is **refused** — the gate would
  have nothing to decide on and the sealed test number would cover no tasks.
  Below 5 val tasks baseline warns: the gate's bar is optimistic at that `n`, and
  a candidate that improves exactly one val task cannot reliably clear it at all
  (issue #351), so size val with the decisions it has to make in mind.

## Reusing a prior baseline (`--reuse-baseline PRIOR_RUN_DIR`)
Re-scoring the seed is wasteful when the split + seed are unchanged.
`--reuse-baseline <prior run_* dir>` (spec key `reuse_baseline`) copies that run's
`splits.json`, `baseline.json`, seed snapshot and seed val rollouts into the fresh
run dir and skips the baseline eval; the copied `test_used` flag is reset so this
run can still finalize on test exactly once. `--resume` is the same-run variant:
reopen an existing run dir, skip the eval when `baseline.json` is already there.
Budget flags (`--max-iterations`, `--stall`, `--max-usd`, …) are accepted here
because the run dir owns the budget and later phases read it from there.

Runs standalone (`/cap-evolve:baseline`) or headlessly via `cap-evolve run`; same
`scripts/run.py` either way.

## How to run
```
python scripts/run.py --base .capevolve --project .capevolve/project \
    --capability seed_capability --seed 0 --ratios 0.5,0.25,0.25 \
    --max-iterations 10 --stall 2
```
Prints the run-dir path (used by the algorithm + finalize), the split sizes, the
baseline val and the headroom verdict. Use `--n-trials ≥ 3` for stochastic
targets so the baseline carries a real `stderr` rather than 0.

The one failure mode nothing later can repair is re-splitting after this phase: a
task migrating out of test leaks the held-out set, and every later number —
including the sealed test score — becomes unfalsifiable.

## References
- `references/concepts.md` — why the split is frozen once and seeded, how to read
  the headroom verdict, and why no-holdout runs are fit metrics, with sources.
