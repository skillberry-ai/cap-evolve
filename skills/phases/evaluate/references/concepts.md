# Concepts — honest, variance-aware evaluation

> A reward without its uncertainty is half a measurement. Agents are stochastic;
> the same candidate scored twice gives two numbers. This note is the statistical
> backbone of `evaluate` (and therefore of the gate, which consumes its `stderr`).
> The implementation is `cap_evolve/stats.py`.

## Two sources of variance, one standard error

When you score a candidate on a split you are estimating a mean across *tasks*,
where each task's score is itself a mean across *trials*. There are two
independent sources of noise:

1. **Within-task (trial) variance** — run the agent on a *fixed* task k times and
   the rewards differ (sampling temperature, tool flakiness, model
   nondeterminism). Captured per task as a trial standard error.
2. **Between-task variance** — tasks differ in difficulty, so the per-task means
   spread out. Captured as the variance of the per-task means.

Reporting only one understates uncertainty. The honest figure folds both into a
**combined standard error** of the overall mean:

```
SE_total = sqrt( between_task_var / n_tasks  +  mean(per_task_SE^2) / n_tasks )
```

This is exactly `cap_evolve.stats.combined_stderr`: the between-task term is the
SE of the task means; the within-task term averages each task's squared trial SE.
The gate compares candidate-vs-current using this combined SE, so getting it
right is what stops the optimizer from "accepting" noise.

**Single trial ⇒ within-task SE is 0** and pass^k/pass@k are undefined. That is
why a stochastic agent scored at `n_trials=1` produces a falsely confident
`stderr` and should never feed a significance gate.

## pass^k vs pass@k — opposite questions

Both summarize k i.i.d. trials on a task, but they measure different things:

- **pass^k (reliability):** probability that **all** k trials pass. Introduced by
  τ-bench, which showed strong models that succeed ~50% of the time per run drop
  far lower under pass^k (e.g. GPT-4o "pass^8 < 25% in retail") — i.e. they are
  not *dependable*. Use pass^k when the agent must work *every* time (customer
  support, automation). With `c` passes of `n` trials the unbiased estimate is the
  hypergeometric `C(c,k) / C(n,k)`.
- **pass@k (capability):** probability that **at least one** of k trials passes.
  Introduced for code generation (Codex/HumanEval), where you can sample many
  candidates and keep any that works. Its unbiased estimator is
  `1 − C(n−c, k) / C(n, k)`, designed to avoid the high variance of naively
  computing `1 − (1 − c/n)^k`.

A candidate can have high pass@k (it *can* solve the task) yet low pass^k (it
*won't reliably*). cap-evolve optimizes capabilities meant to be used repeatedly,
so pass^k is the reliability signal to watch; a wide pass^1 → pass^k drop at
report time means the gain is fragile.

## Bootstrap confidence intervals (when a closed-form SE is not enough)

The combined SE assumes roughly normal task means. For small or skewed task sets,
a **percentile bootstrap** (Koehn 2004) is more robust: resample the per-task
rewards with replacement B times, recompute the mean each time, and take the
2.5th/97.5th percentiles of those means as a 95% CI. `cap_evolve.stats.bootstrap_ci`
implements this deterministically (fixed seed → reproducible CI). Koehn's point —
made for MT metrics but general — is that without resampling you cannot tell
whether a score *difference* is real or an artifact of the particular test items.

## Why evaluate must never touch test

evaluate runs on `train` or `val` only. Every val score informs an accept/reject
decision, so val is "used up" as a tuning signal. The moment test informs *any*
decision during search it stops being held out and the final number becomes a fit
metric. Sealing test for `finalize` is what makes the headline number honest; see
the finalize and gate references.

## Sources
- τ-bench (Yao, Shinn, Razavi, Narasimhan, 2024) — pass^k reliability; the
  per-run-vs-multi-trial gap: https://arxiv.org/abs/2406.12045
- Chen et al., "Evaluating Large Language Models Trained on Code" (2021) — pass@k
  and its variance-reduced unbiased estimator: https://arxiv.org/abs/2107.03374
- Koehn, "Statistical Significance Tests for Machine Translation Evaluation"
  (EMNLP 2004) — bootstrap resampling for score differences:
  https://aclanthology.org/W04-3250/
- `cap_evolve/stats.py` — `combined_stderr`, `pass_k`, `pass_at_k`, `bootstrap_ci`
  (the single auditable place rewards are aggregated).
