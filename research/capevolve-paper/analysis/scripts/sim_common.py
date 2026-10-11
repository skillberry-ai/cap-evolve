"""Shared generative model + thin wrappers around the REAL CapEvolve gate code for the sim_*.py studies.

Pure standard library (numpy/scipy could not be installed on the campaign host: pip downloads were throttled
to ~10 KB/s), so every simulation runs on `random.Random` and multiprocessing. Run with ``python -I``; -I drops
the script dir from sys.path, so sibling modules are imported by inserting this directory explicitly.

What is real: ``gate.decide`` (core/cap_evolve/gate.py:215), ``stats.*`` (stats.py), ``posterior.Pair``
(posterior.py:30), ``objectives.decide_reward_gated`` / ``paired_reward`` and ``harness._paired_deltas``
(harness.py:1024). What is modelled: the benchmark (per-task success probabilities, trial noise, edit effects).
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = os.environ.get("CAPEVOLVE_CORE", str(HERE.parents[3] / "core"))
if CORE not in sys.path:
    sys.path.insert(0, CORE)

from cap_evolve import gate, stats  # noqa: E402

OUT = HERE.parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

mean = stats.mean


def var(xs, ddof=1):
    n = len(xs)
    if n <= ddof:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def seeds(master, n):
    r = random.Random(master)
    return [r.getrandbits(63) for _ in range(n)]


# ----------------------------------------------------------------------------- benchmark model
def draw_base(rng, T, mu=0.55, kappa=1.5):
    """True per-task success probabilities p_i ~ Beta(mu*kappa, (1-mu)*kappa).

    kappa = concentration. kappa~1-2 gives the U-shaped task-difficulty distribution typical of agent
    benchmarks (many always-pass / always-fail tasks); kappa=5 is mild heterogeneity.
    Var(p) = mu(1-mu)/(kappa+1); E[p(1-p)] = mu(1-mu)*kappa/(kappa+1).
    """
    return [rng.betavariate(mu * kappa, (1 - mu) * kappa) for _ in range(T)]


def draw_trials(rng, p, n, icc=0.0):
    """T lists of n binary trials. icc>0 adds within-(arm,task) correlation: each execution batch draws a
    latent rate q ~ Beta(p*c, (1-p)*c), c=(1-icc)/icc, shared by that task's n trials."""
    out = []
    for pi in p:
        pi = min(max(pi, 1e-6), 1 - 1e-6)
        q = pi
        if icc and icc > 0:
            c = (1 - icc) / icc
            q = rng.betavariate(pi * c, (1 - pi) * c)
        out.append([1.0 if rng.random() < q else 0.0 for _ in range(n)])
    return out


def task_means(tr):
    return [mean(r) for r in tr]


def task_ses(tr):
    return [stats.stderr(r) for r in tr]          # the repo's own per-task SE (n-1 variance)


def apply_edit(rng, p, delta, sparse=None):
    """Candidate's true per-task rates for an edit with mean true effect ``delta``.

    sparse=None : diffuse. Every task moves in proportion to its headroom (gain) or its rate (loss).
    sparse=pi   : a random fraction pi of tasks (weighted to tasks with room to move) carries the whole effect.
    """
    T = len(p)
    if delta == 0:
        return list(p)
    w = [(1 - x) if delta > 0 else x for x in p]
    if sparse is None:
        s = mean(w) or 1e-9
        d = [delta * wi / s for wi in w]
    else:
        k = max(1, int(round(sparse * T)))
        keys = sorted(range(T), key=lambda i: -(rng.random() ** (1.0 / (w[i] + 1e-3))))
        idx = keys[:k]
        s = mean([w[i] for i in idx]) or 1e-9
        d = [0.0] * T
        for i in idx:
            d[i] = delta * T / k * (w[i] / s)
    return [min(1.0, max(0.0, x + dx)) for x, dx in zip(p, d)]


# ----------------------------------------------------------------------------- gate wrappers
def paired_decide(par_means, cand_means, *, k_se, coverage=1.0, min_coverage=0.6, floor=0.0, deltas=None):
    """Run the REAL ``gate.decide`` in ``paired`` mode exactly as harness.py:3019 calls it."""
    d = [c - p for c, p in zip(cand_means, par_means)] if deltas is None else list(deltas)
    return gate.decide(mean(par_means), mean(cand_means), split="val", mode="paired", k_se=k_se,
                       paired_deltas=d, paired_se_floor=floor, coverage=coverage, min_coverage=min_coverage)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def fmt_rate(k, n):
    lo, hi = wilson(k, n)
    return f"{k / n:.3f} [{lo:.3f},{hi:.3f}]"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def pool_map(fn, args, procs=None):
    import multiprocessing as mp
    procs = procs or min(56, os.cpu_count() or 4)
    with mp.get_context("fork").Pool(procs) as pool:
        return pool.map(fn, args, chunksize=1)
