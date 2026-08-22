# Concepts — honest, variance-aware evaluation

> A reward without its uncertainty is half a measurement. Agents are stochastic;
> the same candidate scored twice gives two numbers. This note is the statistical
> backbone of `evaluate`. The implementation is `cap_evolve/stats.py`.

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

This is exactly `cap_evolve.stats.combined_stderr` (`stats.py:35-53`): the
between-task term is the SE of the task means; the within-task term averages each
task's squared trial SE. It is the honest SE of the number `evaluate` *reports*.
The gate's `significant` mode compares candidate-vs-current with it
(`gate.py:184-207`) — but that mode is the fallback: the loop's default is `paired`,
which recomputes an SE from the per-task deltas (`gate.py:148-182`) and never reads
this one. See the SKILL.md section "What the gate actually consumes".

**Single trial ⇒ within-task SE is 0** and pass^k/pass@k are undefined. That is
why a stochastic agent scored at `n_trials=1` produces a falsely confident
`stderr` and should never feed a significance gate.

## Small samples: where these statistics stop meaning anything

Both terms above are sample statistics, and they degrade quietly:

- **Below 2 tasks** the between-task variance is defined as 0 (`stats.py:47-50`) and
  `stats.stderr` returns 0 (`stats.py:28-30`). A 1-task val therefore reports
  `stderr = 0`, giving a significance bar of 0; the gate logs a warning and falls
  back to strict, accepting any Δ>0 (`gate.py:40-60, 186-196`).
- **Below roughly 5 tasks** the `k·SE` bar is dominated by sample size rather than by
  the effect, so it is optimistic — a couple of lucky per-task deltas clear it. There
  is no t-based small-sample correction today; issue #113 tracks adding one (and a
  minimum-val-size guard), and its own third bullet asks that the current bar at
  minimum be *documented* as optimistic on tiny val sets. This paragraph is that
  documentation.
- **An empty val** presents as fully covered (`coverage` returns 1.0 when
  `n_tasks == 0`, `loop.py:79-84`) with `reward 0.0` — also issue #113.

### The degenerate single-task delta (issue #351, open)

Under the shipped default gate (`mode: paired`, `k_se: 1.0`), a candidate that
improves exactly one val task by `m` and changes nothing else gives paired deltas
`[m, 0, …, 0]` over `n` tasks:

```
Δ̄   = m/n
var = [ m²(1 − 1/n)² + (n−1)(m/n)² ] / (n−1) = m²/n
SE  = sqrt(var/n) = m/n = Δ̄
```

`Δ̄ == SE` exactly, for every `m` and every `n` — neither a bigger gain nor a bigger
val split rescues it, because both scale identically. Since `gate.py:176` tests a
strict `Δ̄ > k·SE`, the verdict reduces to `x > x` and is settled by floating-point
representation: rejected at n=4, 8, 50; accepted at n=20; identical printed numbers
in every case. So a single-task improvement is not reliably bankable under the
current default, and a rejection of one says nothing about the edit's quality.

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

## Where the test-split refusal is enforced

Not in prose: `scripts/run.py:25` declares `--split` with
`choices=["train", "val"]`, so `--split test` exits 2 with
`invalid choice: 'test'`. Behind that, `harness.evaluate_candidate` reserves the
seal for a test split (`harness.py:240-241`) and `splits.check_test_unused` /
`rundir.begin_test_attempt` raise `TestSealError`. Note the argparse guard is
`evaluate`'s only refusal — `harness.evaluate_candidate(split="test")` is reachable
from any other caller and would write into `rollouts/test/`, which then blocks a
*legitimate* finalize (`rundir.py:385-399`) — issue #361 tracks moving the refusal
into core. Do not widen those choices.

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
