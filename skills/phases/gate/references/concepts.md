# Concepts — the acceptance gate

> The gate is the single rule that decides whether a candidate edit replaces the
> current best. Get it wrong and the optimizer "improves" on noise; the held-out
> number then disappoints and you cannot say why. Implementation:
> `cap_evolve/gate.py` (`decide`).

## Why a gate at all: search amplifies noise

Optimization screens many candidates and keeps the best. If scores are noisy,
the *maximum* over many noisy candidates is biased upward even when nothing truly
improved — the more variants you try, the larger this best-of-noise inflation.
A naive "keep it if the mean went up" rule turns that statistical artifact into a
promoted candidate, and the gain evaporates on held-out data. The gate's job is
to admit only differences large enough that noise is an implausible explanation.

## The significance test (Δ > k·SE)

Each candidate carries a val mean and a standard error. The two means are
independent estimates, so the **standard error of their difference** is:

```
SE_diff = sqrt(SE_candidate^2 + SE_current^2)
```

Accept iff `Δ = candidate − current > k · SE_diff`. This is the
textual-optimization analogue of a two-sample significance test: `k` is how many
standard errors of the difference the gap must clear.

- **k = 1** (default): ~1σ — lenient; lets through gains that are *probably* real
  but lets some noise slip. Good early, when you want momentum.
- **k = 2** (≈ 95% one-sided): stricter; few false accepts, but rejects small real
  gains. Good late, or when each accept is expensive to validate.

Koehn (2004) makes the underlying point for evaluation metrics: a difference in
scores is only meaningful if it survives a significance test (he uses bootstrap
resampling). The `significant` gate enforces the same idea online, per iteration.

**The SE must be real.** With one trial per task the within-task SE is 0, so
`SE_diff` can collapse and `k·SE` → 0, silently turning `significant` into
`strict`. Run multiple trials (see the `evaluate` reference) before trusting the
significance gate.

## No-regression: the second gate

The aggregate mean is a lossy summary. A candidate can lift the mean while
*breaking* tasks the current best solved — net positive, locally harmful. The
fix is a **dual gate**, the discipline that SWE-bench-style evaluation
formalizes: a code patch is accepted only if it makes the target tests pass
(FAIL_TO_PASS) **and** leaves the previously-passing tests passing
(PASS_TO_PASS). Translated here:

> Accept only if (significance gate passes) **and** (no task in the current
> best's passing set regresses).

`diagnose` emits `kept_good` — the currently-passing task ids — exactly so the
no-regression check has a baseline to protect. Without it, hill-climbing on the
mean can quietly trade away reliability.

## The gate runs on val — never train, never test

- **train** is what the optimizer edits against. Gating acceptance on train would
  reward memorizing the data the proposal already saw — pure overfitting.
  `decide` raises `TrainGateError` if asked to gate on train.
- **test** is sealed for `finalize` (scored once). Gating on test would consume
  the held-out set as a tuning signal and make the headline number a fit metric.
- **val** is the honest middle: a held-out-from-training set that every accept
  decision is allowed to consume. It is *expected* to be slightly optimistic by
  the end of search (you selected against it) — which is precisely why the final
  number comes from the untouched test split, not val.

## Modes, briefly

| mode                  | rule                              | when                                  |
|-----------------------|-----------------------------------|---------------------------------------|
| `significant`         | Δ > k·SE                          | default; any stochastic scorer        |
| `strict`              | Δ > 0                             | only near-zero-variance scorers       |
| `threshold`           | Δ > T                             | you have a domain "minimum worth it"  |
| `simplicity_tiebreak` | Δ > 0, else prefer smaller on tie | bias against edits that bloat for free |

## Sources
- Koehn, "Statistical Significance Tests for Machine Translation Evaluation"
  (EMNLP 2004) — bootstrap significance for score differences:
  https://aclanthology.org/W04-3250/
- SWE-bench (Jimenez et al., 2024) — FAIL_TO_PASS *and* PASS_TO_PASS dual-gate:
  https://arxiv.org/abs/2310.06770
- τ-bench (Yao et al., 2024) — reliability under repeated trials motivates
  variance-aware acceptance: https://arxiv.org/abs/2406.12045
- Hastie, Tibshirani, Friedman, *Elements of Statistical Learning* — why
  selection happens on validation and the test set stays sealed:
  https://hastie.su.domains/ElemStatLearn/
- `cap_evolve/gate.py` — `decide` and the `TrainGateError` guard.
