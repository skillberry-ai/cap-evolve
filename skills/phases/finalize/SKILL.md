---
name: finalize
description: Score the best candidate on the held-out TEST split exactly once and seal the run. Use as the last evaluation step, after optimization stops. The run dir enforces the seal — a second finalize raises an error — so the headline number is produced once on data the optimizer never saw, the way an honest benchmark result must be.
component: phase
argument-hint: "--run-dir DIR --project DIR"
allowed-tools: Read, Bash
provides: [report]
needs: [candidate]
sources: [tau2bench]
---

# finalize — the one honest number

Optimization hill-climbs on val: every accept decision consumed the val split as
a tuning signal, so by the end of search val is *optimistic* — it has been
selected against. The number you **report** must come from data nothing was
tuned against. finalize scores the run's best candidate on the sealed `test`
split exactly once and writes `final.json`. That single number is the result.

## Inputs / outputs (manifest tokens)
- **needs:** `candidate` — the run's best candidate (selected on val).
- **provides:** `report` — `final.json` with the test reward, `stderr`, and pass^k.

## The seal (why "exactly once")
`cap_evolve` flips a `test_used` flag the first time test is scored; any second
attempt raises `TestSealError`. This is non-negotiable. The instant test informs
*any* choice — picking between two finalists, "double-checking" a low number,
re-running with more trials until it looks better — it stops being held out. Each
peek is a selection event that leaks information from test into the decision, and
the reported number drifts from an unbiased estimate toward an optimistic fit
metric. Selecting the best of several test scores is exactly the best-of-noise
inflation the gate exists to prevent, now applied to the one split that was
supposed to be clean. The seal makes that mistake impossible rather than merely
discouraged.

Corollary: **all selection happens before finalize.** Choose the single best
candidate on val, *then* finalize it. If you genuinely need to compare two
finalists, compare them on val (or a fresh held-out slice) — never on test.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project --n-trials 3
```
Use multiple trials so the headline carries an honest `stderr` and a pass^k
reliability figure, not a single noisy point. If the split was configured with no
holdout (test == train/val), the number is a *fit* metric and the report must
flag it as such — it is not a held-out result.

## What good vs bad looks like
- **Good:** one best candidate chosen on val, scored once on test with ≥3 trials;
  `final.json` carries reward + stderr + pass^k; test ≈ val (the val gain
  generalized).
- **Bad:** finalizing several candidates and keeping the best test score;
  re-running finalize "to confirm"; reporting a single-trial test number with no
  uncertainty; presenting a no-holdout fit number as if it were held out.

## References
- `references/concepts.md` — held-out sealing, why each peek biases the estimate,
  the selection-before-finalize rule, and how this maps to benchmark protocol,
  with sources.
