---
name: hardest-first
description: An optimization algorithm that scores the seed on the train split once, ranks tasks by reward ascending, and attacks the hardest (lowest-scoring) task first, then cycles in that worst-first order. Use when difficulty is heavy-tailed — a few hard tasks drag the mean down while most pass — and you want budget spent where the marginal gain is largest instead of re-polishing already-easy tasks. Same honest val-only acceptance gate and sealed test split as every algorithm in the family.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer 'CMD {workdir} {prompt}'"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
sources: []
---

# hardest-first

A global hill-climb whose focus schedule is **ordered by difficulty, worst-first**.
It is `cyclic` with a smarter cursor: instead of arbitrary round-robin order, it
ranks tasks by how badly the seed does on them and starts where the headroom is
greatest.

1. **Rank once.** Score the seed candidate on the **train** split, then sort train
   tasks by reward ascending (lowest = hardest first). This ranking is computed a
   single time, up front.
2. **Parent = current global best.** Materialize it (one lineage, like its
   siblings).
3. **Focus the hardest unattended task**, then walk down the ranked list and cycle.
   The reflection emphasizes that task's failure feedback.
4. **Evaluate on val** (`n_trials` rollouts/task) and **gate** on the val
   significance bar. Accept → new best/parent; reject → logged/discarded. Repeat
   until budget / `--max-iterations` / stall.

This is **hard-example mining / anti-curriculum** applied to capability
optimization: concentrate the optimizer's effort on the high-loss tail, because
fixing a task that scores 0.1 has far more headroom than re-polishing one already at
0.95.

## When to use

- **Heavy-tailed difficulty.** Most tasks pass; a few hard ones dominate the loss
  and the mean. Lifting those moves the aggregate most per iteration.
- **Limited budget.** When you can afford only a handful of optimizer calls, spend
  them where the marginal gain is largest rather than spreading them uniformly.
- **Triage.** You want the loop to *prioritize*, not just cover — surface the worst
  problems first so you learn early whether they are even fixable.

## When NOT to use

- **Uniform difficulty** (all tasks roughly equal) — the ordering buys nothing over
  `cyclic`/`all-at-once`, and the upfront train scoring is wasted cost.
- **Very noisy scorers.** The "hardest" ranking is estimated from the seed's train
  scores; under high variance the worst-first order is unstable and may chase noise.
  Raise `--n-trials` so the ranking is trustworthy, or prefer `all-at-once`.
- **A genuinely unsolvable hardest task.** Worst-first can sink the whole budget
  into a task no edit can fix while easier wins go untouched. Cap attention per task
  (cycle onward) or use `cyclic` for even coverage.

## Selection / focus / acceptance behavior

- **Selection (parent):** always the global best — greedy, single lineage. The
  "hardest-first" idea changes *focus order only*, not parent selection.
- **Focus:** the train tasks sorted by ascending seed reward; iteration `i` focuses
  `ranked[i mod N]`, so the hardest is attacked first and the list then cycles. The
  ranking is fixed at the seed's scores (it is not recomputed as candidates change),
  which keeps the schedule stable and cheap.
- **Acceptance:** the shared significance gate on **val** (never train). Crucially,
  the *ranking* uses train scores (cheap, allowed — it only orders effort), while
  *acceptance* still uses held-out val. This separation is what keeps it honest: a
  fix for a hard task is kept only if it improves the held-out aggregate.

## Hyperparameters

- `--max-iterations` (default 10): steps. The hardest tasks are attacked first, so
  even a small budget targets the worst tail.
- `--n-trials` (default 1): rollouts per task per evaluation. Especially important
  here — it stabilizes both the seed ranking *and* the val gate under noise.
- `--gate-mode` (default `significant`) / `--k-se` (default 1.0): the val acceptance
  bar; see `all-at-once` for all modes.
- `--no-regression`: reject candidates that break a previously-passing val task —
  guards against fixing the hardest task at the cost of easy ones.
- `--store`: how accepted iterations are versioned.

Note: `hardest-first` performs one extra **train-split evaluation of the seed** at
startup to build the ranking (cost ≈ `|train| · n_trials` rollouts). Budget for it.

## Trade-offs

- **Strengths:** best aggregate gain per iteration when difficulty is heavy-tailed;
  natural triage that surfaces the worst problems first; concentrates a small budget
  where it counts.
- **Limits:** the ranking is only as good as the seed's (possibly noisy) train
  scores and is not refreshed as the candidate improves; it can over-invest in an
  intractable hardest task; on uniform sets it adds upfront cost for no benefit.
  Like its hill-climb siblings it keeps a single lineage — no diversity/restart
  (that's `gepa-reflective`).

## How to run

```
python scripts/check.py
python scripts/run.py --run-dir .agentcapo/run_XXXX --project .agentcapo/project \
    --optimizer "python <skills>/optimizers/<opt>/scripts/run.py --workdir {workdir} --prompt {prompt}" \
    --max-iterations 10
```

Requires `baseline` first; it then scores the seed on train to build the worst-first
ordering. Routes through `core.harness.hill_climb_loop` with `focus="hardest-first"`
— same loop and honesty as the other schedulers, only the focus order differs.

## References

- `references/concepts.md` — hardest-first as hard-example mining / anti-curriculum,
  the train-ranking vs val-gate split, failure modes, and cited sources.
