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
    else:
        raise RuntimeError(
            f"incomplete beta continued fraction failed to converge in {itmax} "
            f"iterations at a={a!r} b={b!r} x={x!r}"
        )
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


def t_sf(t: float, df: float) -> float:
    """Upper tail P(T > t) for Student's t, computed WITHOUT cancellation.

    This is the tail-space primitive everything else is built on. ``t_cdf`` has to
    form ``1 - tail``, which is exactly ``1.0`` in float64 once ``tail < 1.1e-16``;
    ``t_sf`` never does that subtraction, so it stays accurate into the far tail
    (α down to ~1e-300) and is the only safe thing to root-find against.
    """
    if df <= 0:
        return float("nan")
    if t == 0.0:
        return 0.5
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2.0, 0.5, x)   # P(T > |t|)
    return tail if t > 0 else 1.0 - tail


def t_cdf(t: float, df: float) -> float:
    """P(T <= t) for Student's t with ``df`` degrees of freedom (A&S §26.7.1).

    Note: for ``t`` in the far upper tail this saturates at exactly 1.0 (the tail
    mass is below float64 resolution next to 1). Use ``t_sf`` whenever you care
    about the tail — in particular never root-find on ``1 - alpha`` here.
    """
    if df <= 0:
        return float("nan")
    return 1.0 - t_sf(t, df)


def normal_sf(z: float) -> float:
    """One-sided upper tail P(Z > z) of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


#: The documented supported range for ``k_se``. Above this the inversion is not
#: representable for every df: the answer scales like α^(−1/df), so at df=1 it needs
#: a ``t`` whose square overflows float64 (α ≈ 1e-155 → t ≈ 1e155, t² = inf). 26.5 is
#: the largest z for which every df from 1 upward inverts cleanly. Anything above
#: raises — a k_se this large rejects everything anyway, and returning the
#: uncorrected z bar instead (what the old ``max()`` clamp did) is the one outcome
#: this module must never produce.
MAX_SUPPORTED_K_SE = 26.5


def t_critical(alpha: float, df: float) -> float:
    """One-sided t critical value: the ``t`` with P(T > t) == ``alpha``.

    Bisects on the *survival function* (``t_sf``), never on ``1 - alpha``: the
    latter is exactly 1.0 in float64 for α below ~1.1e-16, which silently turns
    the search into a garbage plateau. Bracketing is geometric so the enormous
    dynamic range (t up to ~1e157 at α~1e-300) is covered, and the answer is
    VERIFIED against ``t_sf`` before it is returned — a wrong critical value in
    the acceptance gate must be an exception, never a number.

    Raises ``ValueError`` for α outside (0, 0.5) or df <= 0 (both are programming
    errors, and a sentinel would get silently multiplied by an SE), and
    ``RuntimeError`` if the solved value does not reproduce ``alpha`` — which is
    the only remaining failure mode, hit when the answer needs a ``t`` so large
    that ``t*t`` overflows float64 (α below ~1e-155 at df=1). Loud, never silent.
    """
    if df <= 0:
        raise ValueError(f"t_critical needs df > 0, got {df!r}")
    if not (0.0 < alpha < 0.5):
        raise ValueError(
            f"t_critical needs 0 < alpha < 0.5, got {alpha!r} "
            "(alpha <= 0 usually means an upstream float64 underflow)"
        )
    lo, hi = 0.0, 1.0
    while t_sf(hi, df) > alpha:
        lo, hi = hi, hi * 2.0
        if hi > 1e300:
            raise RuntimeError(f"t_critical could not bracket alpha={alpha!r} at df={df!r}")
    for _ in range(400):
        mid = (lo + hi) / 2.0
        if t_sf(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * max(1.0, hi):
            break
    t = (lo + hi) / 2.0
    got = t_sf(t, df)
    if not math.isfinite(got) or abs(got - alpha) > 1e-6 * alpha:
        raise RuntimeError(
            f"t_critical failed to invert alpha={alpha!r} at df={df!r}: "
            f"solved t={t!r} has P(T>t)={got!r}"
        )
    return t


def t_multiplier_for_z(k_se: float, n: int) -> float:
    """The t multiplier matching a z multiplier ``k_se`` at sample size ``n``.

    Converts ``k_se`` to its one-sided normal significance level α, then returns
    ``t_{1-α, df=n-1}``. ``t_{1-α,df} >= z_{1-α}`` is a theorem for every finite
    df (t has strictly fatter tails), so no ``max(k_se, ...)`` clamp is needed —
    and a clamp would be actively harmful: its only live effect would be to
    convert a numerically failed inversion into a silent revert to the raw z bar,
    i.e. exactly the bug this correction exists to fix. Invalid input raises.

    Returns ``k_se`` unchanged only when there is genuinely no df (n < 2) or the
    bar is degenerate (k_se <= 0).
    """
    if n < 2 or k_se <= 0:
        return k_se
    if k_se > MAX_SUPPORTED_K_SE:
        raise ValueError(
            f"k_se={k_se} exceeds the supported range (<= {MAX_SUPPORTED_K_SE}): its "
            "one-sided normal tail underflows float64, so no Student-t correction can "
            "be computed. A bar this wide rejects everything anyway — use k_se <= 3."
        )
    alpha = normal_sf(k_se)
    if not (0.0 < alpha < 0.5):
        raise ValueError(
            f"k_se={k_se} maps to a one-sided alpha of {alpha!r}, outside (0, 0.5); "
            "cannot compute a Student-t multiplier."
        )
    return t_critical(alpha, n - 1)
