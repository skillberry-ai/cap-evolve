---
name: baseline
description: Establish the starting point. Use after implement-and-check and before any algorithm. Creates the run directory, freezes the seeded train/val/test split (written once), scores the unmodified seed capability on val, and records it as the candidate every algorithm must beat. Confirms there is headroom to optimize.
component: phase
argument-hint: "--base .agentcapo --project DIR --capability DIR"
allowed-tools: Read, Write, Bash
provides: [splits, baseline, candidate]
needs: [project, tasks]
sources: []
---

# baseline — freeze splits, score the seed

baseline is the first phase that touches data, so it owns the most
consequential one-time decision in the whole run: **the split**. It writes
`splits.json` once (seeded, reproducible), scores the *unmodified* seed
capability on val, and records that score as the candidate every algorithm must
beat. Get the split right here and every downstream number is honest; get it
wrong and nothing later can fix it.

## Inputs / outputs (manifest tokens)
- **needs:** `project` (the implemented adapter) and `tasks` (the dataset).
- **provides:** `splits` (the frozen train/val/test partition), `baseline` (the
  seed's val score), and `candidate` (the seed, registered as the first best).

## Why it matters
- **Fair comparison point.** Every algorithm hill-climbs *against* the baseline
  val score; a candidate that does not beat it is not progress.
- **Headroom check.** If the seed already scores ~1.0 on val, there is little to
  optimize — stop and save budget rather than chase noise. A near-floor baseline,
  conversely, may signal a broken adapter rather than a hard task.
- **Split sealing.** baseline writes the split *once*; from here on no skill
  re-splits, and **test is untouched until finalize**. Freezing it once (seeded)
  guarantees train/val/test stay disjoint and reproducible across reruns — the
  precondition for the honest test number at the end.

## Splitting choices
- **Seeded ratio split** (default `0.5 / 0.25 / 0.25`): deterministic given
  `--seed`. Reproducible runs partition identically.
- **Pinned split** (`--split-ids`): a JSON `{train,val,test}` of ids — use a
  benchmark's official split, or set all three equal to fit the whole set with
  **no holdout** (the report will then flag the test number as a *fit* metric, not
  a held-out result).
- Tasks must be plentiful enough to split three ways and still leave val/test big
  enough that their standard errors are not dominated by sample size.

## How to run
```
python scripts/run.py --base .agentcapo --project .agentcapo/project \
    --capability seed_capability --seed 0 --ratios 0.5,0.25,0.25 \
    --max-iterations 10 --stall 2
```
Prints the run-dir path (used by the algorithm + finalize) and the baseline val.
Use `--n-trials ≥ 3` for stochastic agents so the baseline carries an honest
`stderr` for the gate to compare against.

## What good vs bad looks like
- **Good:** a seeded or official split written once; baseline scored with enough
  trials to have real variance; visible headroom between baseline and 1.0.
- **Bad:** re-splitting later in the run (leaks test); a baseline at ~1.0 chased
  anyway (no headroom — wasted budget); a single-trial baseline `stderr=0` that
  makes every later significance comparison meaningless.

## References
- `references/concepts.md` — why splits are frozen once and seeded, the headroom
  check, no-holdout fit metrics, and the train/val/test contract, with sources.
