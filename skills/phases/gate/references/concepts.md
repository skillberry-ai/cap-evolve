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

Two forms, differing only in how the **standard error of the difference** is computed.

**Paired (`paired`, the default in a real run).** Candidate and current are scored on
the *same* val tasks, so the honest unit of analysis is the per-task difference:

```
Δ[t]    = cand_reward[t] − curr_reward[t]     # over the shared val tasks
SE_diff = sqrt( var(Δ) / n )                  # sample variance, n−1 denominator
accept  ⟺  mean(Δ) > k · SE_diff
```

Pairing cancels the between-task variance — a task that is simply *hard* pulls both
sides down equally and contributes nothing to `var(Δ)` — so the paired test is
substantially more powerful. Its SE also stays non-zero at `num_trials=1`, because it
measures the spread between tasks' *deltas* rather than per-trial noise. That is why
`paired` can bank a single-task gain the unpaired test rejects: fixing one task of `n`
and breaking nothing gives `mean(Δ) = SE_diff = 1/n` exactly, which clears any
`k < 1` (the default `k=1` just misses, since the comparison is strict).

**Unpaired (`significant`).** When the two sides were *not* scored on the same tasks,
the two means are independent estimates, so the SE of their difference is the
root-sum-of-squares of their SEs:

```
SE_diff = sqrt(SE_candidate^2 + SE_current^2)
accept  ⟺  Δ = candidate − current > k · SE_diff
```

Each `SE` here is a `combined_stderr` over *absolute* per-task scores, so it carries
the full between-task spread — on the same data typically a few times larger than the
paired SE, which is exactly the power that pairing recovers.

Either way `k` is how many standard errors of the difference the gap must clear — the
textual-optimization analogue of a two-sample significance test.

- **k = 1** (default): ~1σ — lenient; lets through gains that are *probably* real
  but lets some noise slip. Good early, when you want momentum.
- **k = 2** (≈ 95% one-sided): stricter; few false accepts, but rejects small real
  gains. Good late, or when each accept is expensive to validate.

Koehn (2004) makes the underlying point for evaluation metrics: a difference in
scores is only meaningful if it survives a significance test (he uses bootstrap
resampling). The `significant` gate enforces the same idea online, per iteration.

**The SE must be real.** With one trial per task the within-task SE is 0, so
`SE_diff` can collapse and `k·SE` → 0. The gate does *not* silently become `strict`
when that happens: it logs a `gate_warning` event and applies the documented strict
fallback (`Δ > 0`), tagging the decision `reason` with
`SE=0 → STRICT fallback, warned`. Run multiple trials (see the `evaluate` reference)
before trusting the significance gate. `paired` hits this only at `n=1` shared tasks
or when every task moved identically.

**Small-sample caveat (current behavior).** The bar is a fixed `k · SE` — a z-style
critical value with no t-correction and no minimum-val-size guard — so it is
optimistic on tiny val splits, where a couple of lucky per-task deltas can clear it.
Prefer a val split large enough that between-task spread is meaningful.

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

| mode                  | rule                                   | when                                  |
|-----------------------|----------------------------------------|---------------------------------------|
| **`paired`**          | mean(per-task Δ) > k·SE(Δ), same tasks  | **the default**; most powerful test    |
| `significant`         | Δ(means) > k·sqrt(SE_c²+SE_p²)          | unpaired comparisons; weaker           |
| `threshold`           | Δ > T                                  | you have a domain "minimum worth it"  |
| `strict`              | Δ > 0                                  | only near-zero-variance scorers       |
| `simplicity_tiebreak` | Δ > 0, else prefer smaller on tie      | bias against edits that bloat for free |

`gate.decide`'s `mode=` parameter defaults to `significant` because a bare caller has
no per-task data to pair; the harness passes `paired_deltas` and selects `paired`
itself, and `paired` falls back to `significant` when no deltas are supplied.

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
