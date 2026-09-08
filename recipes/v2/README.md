# recipes/v2/ — divergences between the recipe and the run

`capevolve.v2.2.yaml`, `splits-v2.2.json`, and `patch-harbor-tasks-v2.1.sh` here are
**verbatim copies**. Unlike [`../v1/`](../v1/), this yaml's `split_ids_file` is correctly
wired to a real split file — but the yaml still carries stale comments from v1, and its own
split file disagrees with what the headline run actually recorded.

## 1. Stale v1-era comments describe a different experiment

`capevolve.v2.2.yaml` carries comments such as:

```yaml
split_train: 0.6  # 30 aap2 tasks → 18 train / 6 val / 6 test
...
algorithm_focus: hardest-first  # n=18 train...
```

These describe v1's 30-task, 18-train framing. v2 has 10 tasks, and every one of them is in
*both* `train` and `val` — there is no 18/6/6 split anywhere in this experiment. The
percentages the comments annotate aren't even the active configuration: `split_ids_file:
"splits-v2.2.json"` is set, so `split_train`/`split_val`/`split_test` are dead fields (see
[`../v1/README.md`](../v1/README.md) point 1 for the opposite failure mode — v1 where the
split file is *not* wired up). Whoever forked `capevolve.v2.2.yaml` from v1's yaml updated
the field that mattered (the split file) and left the comments describing the old shape.
If you read this yaml without also reading `splits-v2.2.json`, the comments will actively
mislead you about how many tasks are in play and how they're divided.

## 2. `max_iterations: 5` in the yaml vs. `1` in the run

`capevolve.v2.2.yaml` sets `max_iterations: 5`. The headline run's own `state.json` records
`budget.max_iterations: 1`. This is not a bug in the recipe so much as a fact the recipe
doesn't disclose: per [`../../results/v2/summary.md`](../../results/v2/summary.md), the run
was deliberately driven **one iteration at a time from the shell**, each iteration a
separate `--resume` invocation with its own budget override — not a single `max_iterations:
5` run that happened to stop early. A verbatim rerun of the committed yaml would let
cap-evolve drive up to 5 iterations autonomously in one shot, which is a materially
different execution shape from how the recorded run was actually produced. See
`results/v2/summary.md`'s "The discarded iteration 3" section for what went wrong the one
time a `--resume --run-ts` invocation was used to continue past iteration 1 — it silently
started a fresh run (`run_run_20260818_161550`) instead of resuming, discarding the
champion candidate's edits.

`max_usd: 50.0` and `max_optimizer_usd: 20.0` **do** match `state.json` for this experiment
— unlike v1, budget is not a divergence here.

## 3. The recipe's own split file disagrees with the run's split file on `test_used`

This directory's [`splits-v2.2.json`](splits-v2.2.json) records:

```json
{"test": [], "test_used": false}
```

But the headline run's own `results/v2/runs/run_20260818_161550/splits.json` records:

```json
{"test": [], "test_used": true}
```

Same empty `test: []` list, opposite `test_used` flag. This exact contradiction is what
[`../../results/v2/summary.md`](../../results/v2/summary.md)'s "No holdout" section flags
as cap-evolve's `report.md` making a false "held-out" claim against a split that has nothing
in it — the run believed (or asserted) it had scored a held-out test when the split it used
had zero tasks in that role. The recipe file committed here reflects the *honest* value
(`false`); the run's own recorded state reflects the *claimed* value (`true`). Neither file
was edited after the fact to agree with the other.

**Practical effect: there is no held-out evaluation anywhere in v2.** Every number in
`results/v2/summary.md` is train-fit or val-fit, regardless of what any one run's `report.md`
claims. See that summary's warning box before quoting any v2 number.

## `PROJECT.md` and `patch-harbor-tasks-v2.1.sh`

`PROJECT.md` is the decision log, copied verbatim. `patch-harbor-tasks-v2.1.sh` is the
task-patching script this experiment's yaml expects on `PATH` (or invoked directly) before a
rerun — it stages the `harbor-tasks-v2.1` scenario set the same way v1's
`patch-harbor-tasks.sh` (promoted into `ci/benchmarks/parsec/utils/` on the PR side of this
work) stages v1's.

## What to do if you revive this experiment

Fix the comments so they describe 10 tasks / all-train-and-val / no test, not 30/18/6/6.
Decide whether `test_used` should be `true` or `false` and make both split files agree —
`false` is the honest answer until a real held-out split exists. If you want the actual
execution shape reproduced rather than a fresh 5-iteration autonomous run, drive it
one iteration at a time as the headline run was, and use `--resume` carefully — see the
discarded-iteration-3 postmortem above before trusting `--resume --run-ts` to actually
resume. See [`../../results/v2/summary.md`](../../results/v2/summary.md)'s "Next moves" list
for the fuller case for what a real v2 rerun needs (a model-aware `target_profile` default,
a real held-out split, and an optimizer that writes a journal entry for its own champion).
