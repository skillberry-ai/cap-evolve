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

Optimization hill-climbs on val: every accept decision consumed val as a tuning
signal, so by the end of search val is *optimistic* — it has been selected
against. The number you **report** must come from data nothing was tuned against.
finalize scores the run's best candidate on the sealed `test` split, once, and
writes `final.json`. That file is the run's result.

## One finalize is two evals, not one

A bare test number cannot be defended — a reader cannot tell whether it beat the
capability you started with. So one finalize scores test **twice**: the best
candidate as tag `FINAL`, and the untouched `seed` candidate as `FINAL_seed`
(`harness.finalize`). `final.json` therefore carries `test`, `test_baseline`,
`baseline_id`, and `test_delta` — the held-out *improvement*, which is the figure
`report`, the dashboard, and the event stream all headline. If the best candidate
IS the seed (nothing was accepted), the second eval is skipped and `test_delta` is
0 by construction.

So budget `--n-trials 3` as 3 trials × **2 candidates** × |test| rollouts — twice
what the flag looks like it buys on a paid benchmark.

Both evals sit inside **one** attempt and neither is a selection event: the delta
is *reported*, never chosen on. That is why the seal counts attempts, not evals.

## The seal (why "exactly once")

The instant test informs *any* choice — picking between finalists, "double-
checking" a low number, re-running until it looks better — it stops being held
out, because each peek is a selection event that pulls the number from an
unbiased estimate toward an optimistic fit metric (`references/concepts.md`).

`cap_evolve` enforces this in three parts (`rundir.py:358-407`), and the split
between them is the whole design:

- **reserve** — every `split="test"` eval first *checks* the seal without burning
  it, so no phase other than finalize can reach test at all.
- **commit** — the seal burns only after `final.json` is written, so a finalize
  that dies *before* scoring leaves it unused and is honestly retryable. A
  transient crash must not destroy a run's headline number.
- **attempt guard** — seal-on-success alone cannot tell "crashed before scoring"
  from "crashed after". A real run hit the second case: a finalize killed by a
  timeout had already scored test, the retry scored it again, and the reported
  headline was that second look. `begin_test_attempt` refuses a retry once test
  rollouts exist on disk, before anything is spent.

The seal refuses that mistake by default; it is not unbypassable.
`CAPEVOLVE_ALLOW_TEST_RESCORE=1` is a deliberate opt-in override
(`rundir.py:166`). Its own message promises the use "is recorded in the run" —
nothing records it (issue #341), so a run that took a second look currently looks
identical to an honest one. If you set it, disclose it in the write-up yourself.

Corollary: **all selection happens before finalize.** Choose the single best
candidate on val, *then* finalize it. Finalists that genuinely need comparing get
compared on val — never on test.

## If finalize refuses

A `TestSealError` is three situations with three different right moves. Tell them
apart from `<run>/rollouts/test/` and `test_used` in `splits.json`:

| State | What happened | Do this |
|---|---|---|
| no test rollouts, seal unused | crashed before scoring | Re-run finalize — the case seal-on-success exists for. |
| test rollouts exist, seal unused | crashed after scoring, before commit | Do **not** re-score. Read the rollouts under `<run>/rollouts/test/` and report what that attempt already computed. |
| `test_used: true` | the run is finalized | Read `final.json` and regenerate the human artifact with `report` alone; `cap-evolve run --resume` skips finalize for you. |

Never delete test rollouts or edit `splits.json` to get past the error — that
manufactures a clean-looking number from a split that has already been seen.

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:finalize` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## How to run
```
python scripts/run.py --run-dir .capevolve/run_XXXX --project .capevolve/project --n-trials 3
```
Multiple trials give the headline an honest `stderr` and a pass^k reliability
figure instead of one noisy point. Under `cap-evolve run` the count comes from
`num_trials` in `capevolve.yaml` and **defaults to 1** — set it to ≥3, or the
orchestrated headline ships with `stderr` 0: the exact single point this warns
against. If the split was configured with no holdout (test == train/val) the
number is a *fit* metric, not a held-out result; the dashboard flags it, so say so
in the summary too.

Then read the result instead of just filing it: test ≈ val means the val gain
generalized, test ≪ val means search overfit val — a real finding, not a reason to
re-score.

## References
- `references/concepts.md` — why each peek biases the estimate, the
  train-fits / val-selects / test-estimates rationale, no-holdout runs, and how
  this maps to public benchmark protocol, with sources.
