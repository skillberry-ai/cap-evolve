---
name: evaluate
description: Score a candidate on a split with honest, variance-aware evaluation. Use whenever you need a number for a candidate (the algorithm calls it internally; you can also call it directly to inspect). Runs the target via the adapter for each task, scores each rollout, aggregates mean + standard error, and reports pass^k when trials > 1. Never touches the test split (that is finalize's sealed job).
component: phase
argument-hint: "--run-dir DIR --project DIR --candidate ID --split val"
allowed-tools: Read, Bash
provides: [scores, traces]
needs: [candidate]
---

# evaluate — honest, multi-trial scoring

Turns a candidate into a score you can *trust*. A reward number is only as honest
as the variance around it and as the denominator under it: agents are stochastic,
and infrastructure fails. evaluate produces a point estimate, its uncertainty, and
the count of tasks that actually produced a measurement. The math lives in
`cap_evolve.stats`; this skill drives the adapter and aggregates.

## What it produces
A `SplitResult` (`core/cap_evolve/loop.py:59-115`):
- **`reward`** — the mean, over the tasks that were **scored**, of each task's mean
  over its **valid** trials (`harness.py:405-414`, `loop.py:127-131`). Not the mean
  over every task in the split — see the next section.
- **`n_tasks` / `n_scored`** (and `coverage = n_scored/n_tasks`, `loop.py:79-84`) —
  the honest denominator. Read these on every result, never `reward` alone.
- **`stderr`** — the *combined* SE of that reported mean: between-task variance
  (do different tasks agree?) folded with within-task trial variance (is the agent
  consistent on a fixed task?), `stats.combined_stderr`. This is what the report
  prints and what the gate's `significant` mode consumes — **not** what the default
  gate reads; see "What the gate actually consumes".
- **`pass_k`** — when trials > 1, the estimated probability that **all** k i.i.d.
  trials pass (reliability). Also `pass_at_k` — at least one of k passes
  (capability). Opposite questions; see `references/concepts.md`.
- **per-task scores + feedback**, and the rollout files `diagnose` reads:
  `<run-dir>/rollouts/<split>/<task>__<tag>__t<k>.json` (`harness.py:334`).

## A crashed rollout is missing data, not a zero
The single largest honesty mechanism in the eval path. Two ways a trial produces
no measurement:
- the runner errored (`rollout.error` set) — the target never ran;
- the rollout *succeeded* and the **scorer** could not grade it (crashed grading
  harness, missing report file). There is no `rollout.error`, so adapters must flag
  it by setting `Score.raw["errored"]` (`harness.py:308-323`). An adapter that
  doesn't is how a scorer outage becomes a real 0.0.

Such a trial is excluded from the mean (`harness.py:324-331`), and a task with zero
valid trials is dropped from **every** statistic (`loop.py:118-127`). Averaging its
0.0 in would state that the capability failed a task it was never given — which is
how a registry rate-limit storm produced `val 0.000` and taught the optimizer to
"fix" content that was never at fault. The rollout file is still written, for
forensics.

**What to check.** `raw.valid_trials == 0` on a per-task record means unmeasured,
not failed. A `reward` computed over a third of a split describes the
infrastructure, not the edit. Below `coverage 0.6` the gate returns
`indecisive=True` and declines to judge rather than calling it a regression
(`gate.py:137-146`) — a run producing repeated indecisive steps has an
infrastructure fault, not a bad optimizer. Pinned by
`core/tests/test_infra_errors_not_zeros.py` (518 lines).

## What the gate actually consumes
When per-task data is available the loop sets gate mode to `paired`
(`harness.py:1524-1526`), and paired mode **recomputes** the SE from the per-task
deltas against the same tasks (`gate.py:156-160`); `SplitResult.stderr` is never
read on that path. So what extra trials buy you under the default gate is a more
stable *per-task* mean, which shrinks the paired delta variance — not a smaller
`stderr`. `stderr` feeds the report and the `significant` fallback used when
paired data is unavailable (`gate.py:184-207`).

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project \
    --candidate seed --split val --n-trials 3
```
- `--split` accepts only `train` or `val`, enforced by argparse choices
  (`scripts/run.py:25`) — a `--split test` invocation exits non-zero. The
  enforcement lives in *this CLI*, not in `harness.evaluate_candidate` (issue #361),
  so never "helpfully" widen those choices.
- `--n-trials` **defaults to 1**. On a stochastic target that is the degenerate
  case below; run.py prints a warning to stderr when it happens.
- `--ks` picks the k values for pass^k; it defaults to `1..n_trials`, so
  `--n-trials 3` reports pass^1..pass^3. Any k above a task's trial count is
  omitted rather than reported as 0.0 (`loop.py:134-147`).
- `CAPEVOLVE_WORKERS=N` generates rollouts through a thread pool
  (`harness.py:49-57`); scoring stays serial so the numbers match a serial run.
  Keep it at 1 if `run_target` is not thread-safe (shared scratch dir, one live
  container, module-global client) — `harness.py:225-227`.
- A subset/triage eval (`ids=`) is **never** gateable: its `n_tasks` is the subset,
  so `coverage` reads 1.0 (`harness.py:229-237`).

## How much measurement do you need
Two axes, and the trials axis is the one people get wrong.

- **Trials.** Deterministic scorer + greedy decode: 1 trial is honest. Any
  sampling / temperature / tool nondeterminism: ≥3–4. Trials are only independent
  draws if the adapter **forwards the per-trial seed** — trial `k` runs with
  `seed = base_seed + k` (`harness.py:374`, `trials.py:10-13`) and the adapter
  contract requires passing it to a stochastic runner (`adapter.py:52-54`). An
  adapter that drops it gives you n identical copies: per-task `stderr` is 0,
  `pass^k` is exactly 0 or 1, and the whole apparatus looks healthy while measuring
  nothing. `cap-evolve check` can prove it: with
  `CAPEVOLVE_N_TRIALS=3 CAPEVOLVE_CHECK_TRIAL_PROBE=1` it fires two real rollouts at
  different seeds and warns if they are byte-identical
  (`core/cap_evolve/check.py:169-190`). It is opt-in because the probe costs real
  rollouts — run it once per adapter, and treat the warning as "every variance number
  here is fiction". Trials cost budget linearly, so spend them where variance actually
  threatens a decision — the val split the gate reads — not on every exploratory probe.
- **Tasks.** `stats.stderr` returns 0.0 below 2 tasks and `combined_stderr`'s
  between-task term is 0 below 2 (`stats.py:28-30, 47-50`), so a 1-task val gives
  `stderr = 0`, a bar of 0, and the gate degenerates to strict ("any Δ>0 wins") with
  a logged warning (`gate.py:40-60`). Below roughly 5 val tasks the `k·SE` bar is
  dominated by sample size and is optimistic — issue #113. An empty val presents as
  `coverage 1.0` with `reward 0.0` (`loop.py:79-84`).

**A one-task gain is not reliably bankable.** Under the shipped default
(`mode: paired`, `k_se: 1.0`) a candidate that improves exactly one val task and
changes nothing else has `Δ̄ == SE(Δ)` *algebraically*, so the strict `>` at
`gate.py:176` is settled by floating-point representation — rejected at n=4, 8, 50,
accepted at n=20, identical printed numbers. Issue #351, open; derivation in
`references/concepts.md`. Do not read a rejection of a single-task fix as evidence
the edit was bad — check how many tasks moved.

## What good vs bad looks like
- **Good:** `n_trials ≥ 3` on a stochastic agent with the seed forwarded; `stderr`
  non-zero; `n_scored == n_tasks`; pass^k inspected alongside the mean.
- **Bad:** a plausible low reward that is an infrastructure outage, not a capability
  measurement (check `coverage` first, always); single-trial scores feeding a
  significance gate; identical trial rewards across seeds; trusting a high mean when
  pass^k is low (the gain is fragile).

## References
- `references/concepts.md` (125 lines) — the variance decomposition and the
  combined-SE formula, where these statistics break down on small samples (including
  the #351 `Δ̄ == SE` derivation), pass^k vs pass@k with their unbiased estimators,
  bootstrap CIs, where the test-split refusal is enforced, and sources. Load it when
  you need the statistics themselves rather than how to run an evaluation.
