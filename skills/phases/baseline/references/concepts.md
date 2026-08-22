# Concepts — baseline, splits, and headroom

> baseline owns the split — the one-time decision the rest of the run's honesty
> depends on. This note explains why the split is frozen once and seeded, why the
> headroom check matters, and how no-holdout runs must be labelled.
> Implementation: `harness.ensure_splits` + `harness.baseline`.

## Train / validation / test — the contract baseline seals

cap-evolve follows the standard three-way protocol:

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

## The headroom verdict

baseline scores the *unmodified* seed on val before any optimization, then turns
that number into a budget decision it emits (`headroom`, `headroom_verdict` in the
printed JSON and a `headroom` event in the run dir):

- **`saturated`** (val + stderr ≥ 1.0): the ceiling is already reached. Further
  iterations chase noise for marginal gain — stop and save budget.
- **`floor`** (val ≤ 0): suspicious. Usually a broken adapter (wrong runner,
  mis-wired scorer) rather than a genuinely impossible task. Re-check the contract
  before spending budget.
- **`ok`**: real headroom — proceed.

It is deliberately non-fatal. The verdict is a fact about the run, recorded where
both a human and the orchestrator can read it; deciding to stop is theirs.

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

If the target is stochastic, score the baseline with `--n-trials >= 3`. A
single-trial baseline reports `stderr = 0`, which the gate then inherits for the
rest of the run — see `phases/gate` for what that does to `Δ > k·SE`.

## Sources
- Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning* — the
  train/validation/test protocol and disjointness:
  https://hastie.su.domains/ElemStatLearn/
- τ-bench (Yao et al., 2024) — multi-trial scoring and reliability from the very
  first measurement: https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for MT Evaluation" (EMNLP 2004) — why a
  baseline needs a standard error, not just a point: https://aclanthology.org/W04-3250/
