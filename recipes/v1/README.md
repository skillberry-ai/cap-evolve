# recipes/v1/ — divergences between the recipe and the run

`capevolve.yaml` and `splits.json` here are **verbatim copies** of what shipped in the
source worktree. Running `capevolve.yaml` today, as committed, would **not** reproduce
[`../../results/v1/summary.md`](../../results/v1/summary.md)'s headline run
(`run_20260814_214843`). Three fields disagree with what that run actually did.

## 1. `split_ids_file` is empty — the pin is not wired up

`capevolve.yaml` sets:

```yaml
split_ids_file: ""
split_train: 0.6
split_val: 0.2
split_test: 0.2
split_seed: 0
```

An empty `split_ids_file` means cap-evolve draws its own random 60/20/20 split at
`split_seed: 0` over all 30 tasks. That is not what the headline run scored. Its own
`state.json` and `splits.json` (both reproduced verbatim as
[`splits.json`](splits.json) in this directory) show:

```json
{"train": ["traces_parsec-aap2-0047", "traces_parsec-aap2-0048"],
 "val":   ["traces_parsec-aap2-0047", "traces_parsec-aap2-0048"],
 "test":  ["traces_parsec-aap2-0047", "traces_parsec-aap2-0048"],
 "test_used": true}
```

`train == val == test`, two tasks, not thirty. This is the file
`results/v1/runs/run_20260814_214843/splits.json` actually recorded — it matches
`splits.json` in this directory exactly, but the *yaml* never points at it. Whoever ran the
headline pilot passed the split some other way (by hand, or a since-lost `split_ids_file`
value); the committed yaml doesn't carry that decision forward.

**If v1 is ever rerun from this recipe as-is, it will not optimize against `{0047, 0048}`.**
To reproduce the headline run, set `split_ids_file: "splits.json"` (and drop the
`split_train`/`split_val`/`split_test` percentages, which `run_suite.sh` only reads when no
split file is given).

## 2. `num_trials: 1` — the run used `n=30`

`capevolve.yaml` sets `num_trials: 1`. The headline run's `baseline.json`/`final.json` carry
`n=30` per cell (30 trials against each of the two pinned tasks, at every candidate). A
`num_trials: 1` rerun would produce a single noisy sample per task instead of the 30-trial
distribution the summary's seed-instability finding depends on. Whether `1` was a stale
default never bumped before the recipe was committed, or a deliberate cheap-smoke value,
isn't recorded anywhere in `PROJECT.md` — it's simply a fact the recipe gets wrong.

## 3. Budget: `50.0` / `20.0` in the yaml vs. `100.0` / `40.0` in the run

`capevolve.yaml` sets:

```yaml
max_usd: 50.0
max_optimizer_usd: 20.0
```

The headline run's own `state.json` recorded `budget.max_usd: 100.0` and
`budget.max_optimizer_usd: 40.0` — double the committed recipe. The run never approached
either cap (`spent.optimizer_usd` was `$8.61` over 2 iterations, per
[`../../results/v1/summary.md`](../../results/v1/summary.md)'s cost table), so this
divergence didn't change the outcome — but a verbatim rerun from the committed yaml would be
budget-capped at half of what the recorded run actually had available, which matters if a
future rerun runs more iterations or a costlier optimizer model.

## What to do if you revive this experiment

Fix all three before rerunning, in this order: point `split_ids_file` at `splits.json` (or a
newly-pinned file, if you intend a different split), set `num_trials: 30` to match the
measured distribution, and either raise the yaml's budget to `100.0`/`40.0` or accept that
you're rerunning under a tighter cap than the original. See
[`../../results/v1/summary.md`](../../results/v1/summary.md)'s "Next moves" item A for the
broader case for reviving v1 at all — the 25/30 `trajectory: 0.000` rows are a harness
artifact (2 of 4 kaegis sims down during the sweep), not a skill result, and are worth
re-measuring with the full simulator fleet up before trusting any v1 number that isn't
`-0047`/`-0048`.

## `PROJECT.md`

The decision log, copied verbatim, including a dangling link to `adapters/adapter.py` (that
file isn't reproduced in this branch — see [`../README.md`](../README.md#what-is-deliberately-not-here)
for what recipes/ deliberately omits and why). Read it for the 2026-08-10/2026-08-11 scope
history; it predates the split/trial/budget divergences above and doesn't mention any of
them.
