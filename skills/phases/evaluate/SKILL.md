---
name: evaluate
description: Score a candidate on a split with honest, variance-aware evaluation. Use whenever you need a number for a candidate (the algorithm calls it internally; you can also call it directly to inspect). Runs the target via the adapter for each task, scores each rollout, aggregates mean + standard error, and reports pass^k when trials > 1. Never touches the test split (that is finalize's sealed job).
component: phase
argument-hint: "--run-dir DIR --project DIR --candidate ID --split val"
allowed-tools: Read, Bash
provides: [scores, traces]
needs: [candidate]
sources: [tau2bench]
---

# evaluate — honest, multi-trial scoring

Turns a candidate into a score you can *trust*. A reward number is only as honest
as the variance around it: agents are stochastic, so the same candidate run twice
gives two scores. evaluate's job is to produce a point estimate **and** the
uncertainty that lets the gate decide whether a difference is real. The honesty
math lives in `cap_evolve.stats`; this skill drives the adapter and aggregates.

## Inputs / outputs (manifest tokens)
- **needs:** `candidate` — a capability variant to score (an id in the run dir or
  a directory path).
- **provides:** `scores` (the aggregate `SplitResult`) and `traces` (per-task
  rollouts + feedback — the raw material `diagnose` turns into a learning signal).

## What it produces
A `SplitResult` containing:
- **`reward`** — mean reward across tasks (each task's reward is itself the mean
  over its trials). This is the headline point estimate.
- **`stderr`** — the *combined* standard error: between-task variance (do
  different tasks agree?) folded together with within-task trial variance (is the
  agent consistent on a fixed task?). One SE that honestly reflects both sources
  of noise — not the smaller of the two.
- **`pass_k`** — when trials > 1, the estimated probability that **all** k i.i.d.
  trials pass (τ-bench reliability). Optionally `pass@k`, the probability that
  **at least one** of k trials passes (capability). They answer opposite
  questions; see `references/concepts.md`.
- **per-task scores + feedback** — the learning signal `diagnose` reads.

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:evaluate` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project \
    --candidate seed --split val --n-trials 3
```
`--split` accepts only `train` or `val` — **evaluate can never touch test.**
Test belongs to `finalize`, which scores it exactly once. Use multiple trials
when the target is stochastic: a single trial reports `stderr=0`, which is a lie
that lets the gate accept noise as progress.

## Choosing the number of trials
- **Deterministic scorer + greedy decode (temp 0):** 1 trial is honest.
- **Any sampling / temperature / tool nondeterminism:** ≥3–4 trials. More trials
  shrink `stderr` ∝ 1/√(trials) and make pass^k / pass@k estimable.
- Trials cost budget linearly. Spend them where variance actually threatens the
  decision — usually on the val split the gate reads, not on every probe.

## What good vs bad looks like
- **Good:** `n_trials ≥ 3` on a stochastic agent; `stderr` reported and non-zero;
  pass^k present and inspected alongside the mean.
- **Bad:** single-trial scores on a stochastic agent feeding a significance gate
  (every marginal "win" is noise); reading the test split "just to check"; trusting
  a high mean when pass^k is low (the gain is fragile across trials).

## References
- `references/concepts.md` — variance decomposition, combined standard error,
  pass^k vs pass@k with their unbiased estimators, multi-trial budgeting, and
  bootstrap CIs, with sources.
