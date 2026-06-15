"""Variance-aware statistics — the math behind honest evaluation.

Pure stdlib. These functions are the *only* place rewards get aggregated, so
the discipline (mean over trials, combined within/between variance, pass^k)
lives in one auditable spot rather than being re-derived per algorithm.

References:
- tau-bench / tau2-bench pass^k (probability all k i.i.d. trials succeed).
- prior agent-optimization work ``eval/base.py`` combined_stderr (mixes between-sample and within-sample
  trial error).
"""

from __future__ import annotations

import math
from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def stderr(xs: Sequence[float]) -> float:
    """Standard error of the mean across samples."""
    xs = list(xs)
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var / n)


def combined_stderr(per_task_means: Sequence[float], per_task_stderrs: Sequence[float]) -> float:
    """Total SE of the overall mean, mixing between-task and within-task error.

    between-task: variance of the per-task means / n_tasks.
    within-task:  mean of per-task squared SEs / n_tasks (each task mean already
                  carries its own trial error).
    """
    means = list(per_task_means)
    ses = list(per_task_stderrs)
    n = len(means)
    if n == 0:
        return 0.0
    between_var = 0.0
    if n >= 2:
        m = mean(means)
        between_var = sum((x - m) ** 2 for x in means) / (n - 1)
    between_se_sq = between_var / n
    within_se_sq = sum(s * s for s in ses) / (n * n) if ses else 0.0
    return math.sqrt(between_se_sq + within_se_sq)


def pass_k(trial_rewards: Sequence[float], k: int, threshold: float = 1.0) -> float:
    """pass^k: estimated probability that k independent trials all 'pass'.

    A trial 'passes' when its reward >= threshold (default exact success). With
    ``c`` passes out of ``n`` trials, the unbiased estimate of all-k-pass is the
    hypergeometric C(c, k) / C(n, k). Returns 0 when k > n.
    """
    rewards = list(trial_rewards)
    n = len(rewards)
    if k <= 0 or k > n:
        return 0.0
    c = sum(1 for r in rewards if r >= threshold)
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def pass_at_k(trial_rewards: Sequence[float], k: int, threshold: float = 1.0) -> float:
    """pass@k: estimated probability that AT LEAST ONE of k trials passes.

    Capability (vs pass^k's reliability). With c passes of n trials, the chance
    that a random k-subset contains no pass is C(n-c, k)/C(n, k); pass@k is its
    complement. Returns 1 if any trial passes and k>=n.
    """
    rewards = list(trial_rewards)
    n = len(rewards)
    if k <= 0 or n == 0:
        return 0.0
    k = min(k, n)
    c = sum(1 for r in rewards if r >= threshold)
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - (math.comb(n - c, k) / math.comb(n, k))


def bootstrap_ci(xs: Sequence[float], confidence: float = 0.95, resamples: int = 2000,
                 seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean (Koehn'04). Deterministic given seed."""
    import random
    xs = list(xs)
    n = len(xs)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (xs[0], xs[0])
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        means.append(sum(xs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo_i = int((1 - confidence) / 2 * resamples)
    hi_i = int((1 + confidence) / 2 * resamples) - 1
    return (means[max(0, lo_i)], means[min(resamples - 1, hi_i)])


def aggregate(per_task_means: Sequence[float]) -> float:
    """Headline score = mean reward across tasks."""
    return mean(per_task_means)
