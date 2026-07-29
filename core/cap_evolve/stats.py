"""Variance-aware statistics — the math behind honest evaluation.

Pure stdlib. These functions are the *only* place rewards get aggregated, so
the discipline (mean over trials, combined within/between variance, pass^k)
lives in one auditable spot rather than being re-derived per algorithm.

References:
- tau-bench / tau2-bench pass^k (probability all k i.i.d. trials succeed).
- prior agent-optimization work ``eval/base.py`` combined_stderr (mixes between-sample and within-sample
  trial error).
- Student's t CDF via the regularized incomplete beta function: Abramowitz &
  Stegun, *Handbook of Mathematical Functions* (1964) §26.7.1; the continued
  fraction for I_x(a,b) is Numerical Recipes in C (2nd ed.) §6.4 ``betacf``
  with Lentz's modification.
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


# ---- small-sample (Student's t) machinery ---------------------------------
#
# Why this exists: the significance gate's bar is ``k·SE``, i.e. a *z* multiplier.
# That is only valid when SE is known / n is large. With n val tasks the paired SE
# is ESTIMATED from the same n deltas, so the standardized mean difference follows
# a t distribution with df = n-1, whose tails are fatter than the normal's. Using
# z at small n therefore sets the bar TOO LOW and accepts noise — precisely the
# failure the gate exists to prevent. ``t_critical`` returns the t multiplier at
# the same one-sided significance level as the requested z, so the bar widens at
# small n and converges to k as n grows.


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (NR in C 2e §6.4)."""
    tiny, eps, itmax = 1e-30, 3e-16, 300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b). Stdlib-only (A&S §26.5.8)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """P(T <= t) for Student's t with ``df`` degrees of freedom (A&S §26.7.1)."""
    if df <= 0:
        return float("nan")
    if t == 0.0:
        return 0.5
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2.0, 0.5, x)   # P(T > |t|)
    return 1.0 - tail if t > 0 else tail


def normal_sf(z: float) -> float:
    """One-sided upper tail P(Z > z) of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def t_critical(alpha: float, df: float) -> float:
    """One-sided t critical value: the ``t`` with P(T > t) == ``alpha``.

    Solved by bisection on the monotone CDF — no scipy, no lookup table, exact to
    1e-10 for any df >= 1 (so it also covers non-integer k_se-derived alphas).
    """
    if df <= 0 or not (0.0 < alpha < 0.5):
        return float("inf") if df <= 0 else 0.0
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < 1.0 - alpha and hi < 1e12:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < 1.0 - alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-11:
            break
    return (lo + hi) / 2.0


def t_multiplier_for_z(k_se: float, n: int) -> float:
    """The t multiplier matching a z multiplier ``k_se`` at sample size ``n``.

    Converts ``k_se`` to its one-sided normal significance level α, then returns
    ``t_{1-α, df=n-1}``. Always >= ``k_se`` (t tails are fatter than z), so the
    gate can only get STRICTER; the ratio → 1 as n grows.
    Returns ``k_se`` unchanged when there is no usable df (n < 2).
    """
    if n < 2 or k_se <= 0:
        return k_se
    alpha = normal_sf(k_se)
    if not (0.0 < alpha < 0.5):
        return k_se
    return max(k_se, t_critical(alpha, n - 1))
