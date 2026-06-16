---
name: cyclic
description: An optimization algorithm that focuses one training task at a time, cycling round-robin through them and skipping tasks already solved, while the parent stays the global best. Use when failures are heterogeneous — different tasks fail for different reasons — so per-task attention beats a single averaged global edit, or to break a plateau after the all-at-once global hill-climb stalls. Same honest val-only acceptance gate and sealed test split as every algorithm in the family.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}'"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
sources: [governor]
---

# cyclic

A global hill-climb whose **focus rotates round-robin over the training tasks**.
The parent is always the current best candidate (one lineage, as in `all-at-once`);
the only difference is that each iteration's reflection narrows to a **single
task** instead of the whole set:

1. **Parent = current global best.** Materialize it into a fresh working copy.
2. **Pick the focus task.** Iteration `i` selects `train[i mod N]`. The reflection
   emphasizes that task's failure (its feedback), so the optimizer addresses one
   concrete problem at a time. Tasks already passing are effectively skipped — a
   solved task contributes no failing feedback to focus on.
3. **Evaluate on val** (`n_trials` rollouts/task) and **gate** on the val
   significance bar. Accept → new best/parent; reject → logged and discarded.
4. **Advance the cursor** and repeat until budget / `--max-iterations` / stall.

The intuition is **coordinate-ascent / round-robin descent**: rather than moving
along the averaged gradient of all failures at once (which can be pulled in
conflicting directions), improve one coordinate (task) per step. This is the
classic move when a single global edit can't satisfy everything simultaneously.

## When to use

- **Heterogeneous failures.** Tasks fail for *different* reasons, so one global edit
  has to trade them off and tends to average them away. Per-task focus lets the
  optimizer write a targeted fix for each in turn.
- **To break an all-at-once plateau.** When the global hill-climb has stalled
  (several rejects in a row), narrowing the focus often finds a move the averaged
  reflection missed.
- **Fairness / coverage.** Round-robin guarantees every task gets attention over a
  cycle, instead of the loop fixating on whatever dominates the mean.

## When NOT to use

- **Homogeneous tasks** (all fail the same way) — `all-at-once` reaches the same fix
  in one edit and is cheaper.
- **Heavy-tailed difficulty**, where a few tasks dominate the loss — prefer
  `hardest-first`, which spends budget worst-first instead of giving every task an
  equal slot.
- **When you have rich execution traces and want a kept population** — prefer
  `gepa-reflective` (per-task Pareto frontier + trace reflection).

## Selection / focus / acceptance behavior

- **Selection (parent):** always the global best — pure greedy hill-climb, one
  lineage. Cyclic does *not* keep a population; it only changes what each step looks
  at.
- **Focus:** `train[i mod N]` each iteration. Solved tasks present no failing
  feedback, so the effective schedule cycles through the *unsolved* tasks. A full
  pass touches every task once before repeating.
- **Acceptance:** the shared significance gate on **val** (never train). A per-task
  edit must still improve the *held-out* aggregate to be kept — so the gate guards
  against fixing the focus task by breaking others (and `--no-regression` makes that
  guard hard).

## Hyperparameters

- `--max-iterations` (default 10): with `N` train tasks, `⌈max_iterations / N⌉`
  full passes. Give it at least one full cycle so every task gets a turn.
- `--n-trials` (default 1): rollouts per task per evaluation; raise under a noisy
  scorer.
- `--gate-mode` (default `significant`) / `--k-se` (default 1.0): the acceptance
  bar (Δ > `k_se`·SE). See `all-at-once` for the full list of modes.
- `--no-regression`: reject any candidate that breaks a val task the parent passed —
  especially valuable here, since a single-task fix is the most likely to regress a
  sibling.
- `--store`: how accepted iterations are versioned.

## Trade-offs

- **Strengths:** isolates one problem per step, so each optimizer call gets a clean,
  concrete signal; naturally covers the whole set; reliably escapes the "averaging"
  plateau of a global edit.
- **Limits:** spends equal budget on easy and hard tasks (no triage — that's
  `hardest-first`'s job); a fix for the focus task can regress others (mitigate with
  `--no-regression`); on a homogeneous set it wastes iterations re-deriving the same
  general fix one task at a time. Still a single lineage, so no diversity / restart
  mechanism — a Pareto method (`gepa-reflective`) can escape local optima it can't.

## How to run

```
python scripts/check.py
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project \
    --optimizer "python <skills>/optimizers/<opt>/scripts/run.py --workdir {workdir} --prompt {prompt}" \
    --max-iterations 10
```

Requires `baseline` first. Differs from `all-at-once` only in the focus schedule;
both route through `core.harness.hill_climb_loop` (here with `focus="cyclic"`).

## References

- `references/concepts.md` — cyclic as coordinate-ascent / round-robin scheduling,
  its relation to per-task feedback methods and curriculum scheduling, and cited
  sources.
