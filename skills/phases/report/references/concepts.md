# Concepts — reading a run honestly

> A report's job is not to make the run look good; it is to let a human decide
> whether to ship. The honest reading is always test-vs-baseline, with the
> val-test gap as the overfitting it is. Implementation: this skill's
> `scripts/run.py` + `scripts/dashboard.py`.

## The three numbers, and what their relationships mean

| relationship          | interpretation                                          | action            |
|-----------------------|---------------------------------------------------------|-------------------|
| test ≈ baseline       | no real gain (val gain was noise/overfit)               | don't ship; retune|
| test ≫ baseline       | genuine improvement on unseen data                      | ship              |
| val ≫ test            | overfitting — learned the val set, not the capability   | the gap is the leak|
| high mean, low pass^k | gain is fragile across trials (unreliable)              | not a dependable win|

- **baseline (val)** — where the unmodified seed started.
- **best (val)** — where search landed *on the split it optimized against*. This
  is expected to be optimistic; it is not the result.
- **test** — scored once, on data nothing was tuned against. This is the result.

## The val–test gap is overfitting, quantified

Search selects the candidate that scores best on val, so the final val score is
biased upward by exactly the amount of selection performed. The test score has no
such bias. Their difference is therefore a direct measurement of how much the run
overfit the val split. A small gap means the val gains generalized; a large gap
means the optimizer learned the validation tasks rather than the capability. Report
the gap honestly — it is one of the most informative numbers in the run, and
hiding it (by quoting val as "the result") is the most common way optimization
reports mislead.

## Reliability: pass^k, not just the mean

A high mean reward can hide an unreliable agent — one that passes often but not
*every* time. τ-bench showed strong agents whose per-run success looked fine but
whose pass^k collapsed (succeeding on all of k repeated trials is much harder than
succeeding once). At report time, a wide pass^1 → pass^k drop is a flag: the gain
exists but is fragile. For any capability that must work repeatedly, pass^k is the
number that decides shippability, not the mean.

## Always report uncertainty

A point estimate without its standard error or confidence interval invites
over-reading. "0.71" and "0.71 ± 0.08" justify different decisions; a 3-point test
gain inside a ±8-point CI is not a result. Carry the combined stderr (or a
bootstrap CI) from finalize into the report so the reader sees the noise floor, not
just the headline.

## No-holdout runs

If the run was configured with no holdout (test == train/val), say so plainly: the
test number is a *fit* metric (how well it fits data it was tuned on), not an
estimate of generalization. The dashboard and `report.md` should label it so no
reader mistakes a fit for a held-out result.

## Sources
- τ-bench (Yao et al., 2024) — pass^k reliability and the per-run-vs-multi-trial
  gap: https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for MT Evaluation" (EMNLP 2004) —
  reporting differences with uncertainty: https://aclanthology.org/W04-3250/
- Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning* — the
  validation–test gap as a measure of optimism/overfit:
  https://hastie.su.domains/ElemStatLearn/
