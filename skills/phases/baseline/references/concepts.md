# Concepts — baseline, splits, and headroom

> baseline owns the split — the one-time decision the rest of the run's honesty
> depends on. This note explains why the split is frozen once and seeded, why the
> headroom check matters, and how no-holdout runs must be labelled.
> Implementation: `harness.ensure_splits` + `harness.baseline`.

## Train / validation / test — the contract baseline seals

agent-capo follows the standard three-way protocol:

- **train** — the data the optimizer edits *against* (proposes changes from).
- **val** — the data acceptance is decided on (the gate reads it every iteration).
- **test** — scored *once*, at finalize, to estimate generalization.

baseline writes this partition to `splits.json` exactly once. Freezing it has two
purposes:

1. **Disjointness.** If a later phase re-split, a task could migrate from test
   into train/val, leaking the held-out set and inflating the final number. One
   write, never rewritten, makes that impossible.
2. **Reproducibility.** A seeded split means two runs with the same seed partition
   identically, so results are comparable and bugs are reproducible. The seed is
   recorded in the run dir.

## The headroom check

baseline scores the *unmodified* seed on val before any optimization. The val
number is a budget decision:

- **Seed ≈ 1.0:** the ceiling is already reached. Optimizing further chases noise
  for marginal gain — stop and save budget.
- **Seed ≈ floor (near 0):** suspicious. Often a broken adapter (wrong runner,
  mis-wired scorer) rather than a genuinely impossible task. Re-check the
  contract before spending budget.
- **Seed in the middle:** real headroom — proceed.

Recording the baseline also gives every algorithm a fixed bar: a candidate must
beat the baseline val (by the gate's significance margin) to count as progress.
Without a frozen baseline, "improvement" has no reference point.

## No-holdout runs are fit metrics, not held-out results

Sometimes the task set is too small to split three ways and the user pins all
three splits equal (fit the whole set). That is a legitimate choice, but it means
the "test" number was computed on data the optimizer tuned against — a **fit
metric**, not an estimate of generalization. baseline still runs; the report must
flag the test number accordingly so no reader mistakes it for held-out
performance. The distinction is the difference between "fits the data we have" and
"works on data we have not seen".

## Variance starts here

If the agent is stochastic, score the baseline with multiple trials. A
single-trial baseline reports `stderr = 0`, and since the gate compares each
candidate against the baseline using a combined standard error, a zero baseline SE
quietly weakens every later significance test. Honest variance at the baseline is
what lets the gate reject noise for the rest of the run.

## Sources
- Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning* — the
  train/validation/test protocol and disjointness:
  https://hastie.su.domains/ElemStatLearn/
- τ-bench (Yao et al., 2024) — multi-trial scoring and reliability from the very
  first measurement: https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for MT Evaluation" (EMNLP 2004) — why a
  baseline needs a standard error, not just a point: https://aclanthology.org/W04-3250/
