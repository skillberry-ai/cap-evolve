---
name: all-at-once
description: The simplest, most robust optimization algorithm — a global hill-climb that proposes one edit against the whole training set every iteration, keeping the current best candidate as the parent. Use this as the default/first algorithm, as the baseline that fancier schedulers (cyclic, hardest-first, gepa-reflective) must beat to justify their complexity, or when the task set is small and homogeneous. A candidate is accepted only if it beats the held-out val set by the significance gate; the test split stays sealed for finalize.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}'"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
sources: [evo]
---

# all-at-once

A **global hill-climb** over candidate capabilities (a prompt, skill, or tool
text). Every iteration does one propose → evaluate → gate step:

1. **Parent = current global best.** Materialize the best-scoring candidate so far
   into a fresh working copy.
2. **Propose against the *whole* train set.** Build one reflection that surfaces
   every currently-failing val task and asks the optimizer to raise the aggregate
   score with a single edit — no per-task focus, no ordering.
3. **Evaluate on val** (`n_trials` rollouts per task, aggregated with a standard
   error).
4. **Gate.** Accept iff the val delta clears the significance bar
   (`Δ > k_se · combined_SE`). On accept, the candidate becomes the new best and
   parent of the next iteration; on reject it is logged to memory and discarded.

Repeat until `--max-iterations`, the budget, or the stall condition is hit. This
is the canonical (1+1) / steepest-ascent loop from evolutionary search and the
prompt-optimization literature (APE, OPRO, ProTeGi) reduced to its simplest honest
form: one parent, one offspring per step, accept on a held-out improvement.

## When to use

- **Your first run.** Fewest moving parts, fewest failure modes, easiest to reason
  about. Start here unless you already know the failure structure favors a
  specialized scheduler.
- **As the baseline.** The honest way to decide whether `cyclic`,
  `hardest-first`, or `gepa-reflective` *earns* its complexity is to beat
  all-at-once on the same budget and splits. If it doesn't, prefer this.
- **Small or homogeneous task sets**, where per-task scheduling buys little because
  all tasks fail for essentially the same reason — one global edit fixes many.

## How it differs from its siblings

All four algorithms share the same honest core (val-only acceptance gate, sealed
test, multi-trial scoring). They differ only in **what each step focuses on** and
**which parent it extends**:

- **all-at-once** — parent = global best; focus = the entire train set.
- **cyclic** — parent = global best; focus = one not-yet-solved task, round-robin.
- **hardest-first** — parent = global best; focus = the lowest-scoring task first,
  then cycle.
- **gepa-reflective** — parent = sampled from a per-task **Pareto frontier** (keeps
  specialists, not just the single best); focus = a reflective trace dataset.

all-at-once is the degenerate case of the others: no ordering, no per-task
narrowing, no frontier. That simplicity is exactly why it is the right default and
the right yardstick.

## Selection / focus / acceptance behavior

- **Selection (parent):** always the current best (pure greedy hill-climb). No
  population, no restart — one lineage.
- **Focus:** none. The reflection lists *all* failing val tasks (truncated for
  prompt budget) and asks for one general improvement.
- **Acceptance:** the shared significance gate on **val**. Gating on train would
  overfit the optimizer to the very data it edits against, so the core refuses it.

## Hyperparameters

- `--max-iterations` (default 10): propose→gate steps. The dominant cost knob; each
  step is one optimizer call + one val evaluation.
- `--n-trials` (default 1): rollouts per task per evaluation. Raise it when the
  scorer is noisy — it shrinks the standard error so the gate can resolve real
  gains; it linearly increases cost.
- `--gate-mode` (default `significant`): `significant` (Δ > `k_se`·SE, honest),
  `threshold` (flat margin), `strict` (any Δ > 0), or `simplicity_tiebreak`
  (prefer the smaller candidate on a tie).
- `--k-se` (default 1.0): how many standard errors of improvement the gate demands.
  Higher = stricter (fewer false accepts, slower progress); lower = looser.
- `--no-regression`: a SWE-bench-style dual gate — even if the mean improves,
  reject any candidate that breaks a val task the parent already passed.
- `--resume`: continue from the run's current best (its val read back from saved
  rollouts) instead of from `baseline`.
- `--store` (`git`|`copy`|`command`): how each accepted iteration is versioned so
  the whole process stays inspectable.

## Trade-offs

- **Strengths:** minimal variance, easy to debug, no scheduling assumptions, hard
  to make worse — it can only accept held-out improvements. Best sample efficiency
  when failures are correlated.
- **Limits:** a single global edit can be pulled in conflicting directions when
  failures are heterogeneous, so it can **plateau** — different tasks need
  different fixes and the optimizer averages them away. When that happens, switch
  to `cyclic`/`hardest-first` (narrower focus) or `gepa-reflective` (frontier +
  trace reflection). It also has no diversity mechanism, so it can get stuck in a
  local optimum that a population-based method would escape.

## How to run

```
python scripts/check.py
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project \
    --optimizer "python <skills>/optimizers/<opt>/scripts/run.py --workdir {workdir} --prompt {prompt}" \
    --max-iterations 10 --n-trials 1 --gate-mode significant --k-se 1.0
```

Requires `baseline` to have run first (it sets the seed candidate and its val
score). The optimizer is any command that edits the files in `{workdir}` in place,
given the reflection at `{prompt}`. Mechanics (splits, multi-trial scoring, gate,
sealed test) live in `core.harness.hill_climb_loop` with `focus="all"`; this skill
only selects the schedule.

## References

- `references/concepts.md` — the global hill-climb / (1+1)-style loop, its place in
  the prompt-optimization and evolutionary-search literature, and cited sources.
