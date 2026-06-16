# Concepts — finalize and held-out sealing

> The whole pipeline exists to produce *one* number you can defend: how good is
> the optimized capability on data nothing was tuned against. finalize produces
> it, once, and the run dir enforces that "once". Implementation:
> `harness.finalize` + the `test_used` seal in `cap_evolve/rundir.py`.

## Why val is not the answer

During search, every accept/reject decision read the val split. Selecting the
candidate that scores best on val means val has been *optimized against* — its
score is biased upward by exactly the selection you performed (the more
candidates you screened, the larger the bias). This is the standard reason ML
keeps a third split: train fits, validation selects, **test estimates**. The test
number is trustworthy only because nothing — no edit, no acceptance, no
hyperparameter — was ever chosen using it.

## The seal: why "exactly once" is mechanical, not advisory

A held-out set stays held out only while it is untouched. Each time you score
test you create an opportunity to *act* on the result:

- "The number looks low — let me try the second-best candidate on test too."
- "Let me re-run with more trials until it stabilizes."
- "Let me double-check after one more edit."

Every one of these is a selection event. Picking the best of several test scores
is the same best-of-noise inflation the acceptance gate guards against — now
applied to the one split that was supposed to be clean. The result is no longer
an unbiased estimate; it has quietly become a fit metric, and nothing in the
output says so.

cap-evolve refuses to let this happen by accident: `RunDir` flips `test_used` on
the first test scoring, and any second attempt raises `TestSealError`. The
honesty is enforced by the harness, not left to the operator's discipline.

## Selection happens before finalize

The corollary is a workflow rule: **all model selection must complete on val (or
train) before finalize runs.** Choose the single best candidate, then finalize it.
If two finalists genuinely need comparing, compare them on val or a freshly
carved held-out slice — never on test. finalize takes `run_dir.best_id` (already
chosen on val) precisely so the choice is made before the seal is touched.

## Report the uncertainty, and flag no-holdout runs

A single-trial point estimate on test is honest about the split but dishonest
about variance. Use ≥3 trials so `final.json` carries `stderr` and a pass^k
reliability figure alongside the mean — a high mean with low pass^k is a fragile
result the report should surface. And if the run was configured with no holdout
(test == train/val, e.g. to fit a tiny task set), the number is a *fit* metric,
not a held-out estimate; the report must label it so no reader mistakes it for
generalization.

## Mapping to benchmark protocol

Public benchmarks institutionalize this same seal: a hidden test set, a
submission scored once, no resubmission tuning. τ-bench additionally reports
pass^k so the headline reflects *reliability* across trials, not a single lucky
run. finalize is the local, enforced version of that protocol for a single
optimization run.

## Sources
- Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning* — train
  fits / validation selects / test estimates; why test stays sealed:
  https://hastie.su.domains/ElemStatLearn/
- τ-bench (Yao et al., 2024) — scoring once and reporting pass^k reliability:
  https://arxiv.org/abs/2406.12045
- Koehn, "Statistical Significance Tests for MT Evaluation" (EMNLP 2004) — why a
  reported difference needs uncertainty, not a bare point:
  https://aclanthology.org/W04-3250/
- `cap_evolve/rundir.py` — the `test_used` flag and `TestSealError`.
