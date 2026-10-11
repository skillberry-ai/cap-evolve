"""Shared generative model + thin wrappers around the REAL CapEvolve gate code for the sim_*.py studies.

Run with ``python -I``; -I drops the script dir from sys.path, so this module is imported by
inserting its own directory explicitly (see each sim_*.py header).

What is real: ``gate.decide`` (core/cap_evolve/gate.py:215), ``stats.*``, ``posterior.Pair`` (posterior.py:30),
``objectives.decide_reward_gated`` / ``paired_reward`` and ``harness._paired_deltas`` (harness.py:1024).
What is modelled: the benchmark (per-task success probabilities, trial noise, edit effects).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CORE = os.environ.get("CAPEVOLVE_CORE", str(HERE.parents[3] / "core"))
if CORE not in sys.path:
    sys.path.insert(0, CORE)

from cap_evolve import gate, stats  # noqa: E402

OUT = HERE.parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------- benchmark model
def draw_base(rng, T, mu=0.55, kappa=1.5):
    """True per-task success probabilities p_i ~ Beta(mu*kappa, (1-mu)*kappa).

    kappa = concentration. kappa~1-2 gives the U-shaped task-difficulty distribution typical of
    agent benchmarks (many always-pass / always-fail tasks); kappa=5 is mild heterogeneity.
    Var(p) = mu(1-mu)/(kappa+1); E[p(1-p)] = mu(1-mu)*kappa/(kappa+1).
    """
    return rng.beta(mu * kappa, (1 - mu) * kappa, size=T)


def draw_trials(rng, p, n, icc=0.0):
    """T x n binary trial matrix. icc>0 adds within-(arm,task) correlation: each execution batch
    draws a latent rate q ~ Beta(p*c, (1-p)*c), c=(1-icc)/icc, shared by that task's n trials."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    if icc and icc > 0:
        c = (1 - icc) / icc
        q = rng.beta(p * c, (1 - p) * c)
    else:
        q = p
    return (rng.random((len(p), n)) < q[:, None]).astype(float)


def per_task(trials):
    """(means, stderrs) per task using the repo's own stats.stderr (n-1 variance)."""
    means = trials.mean(axis=1)
    ses = np.array([stats.stderr(list(r)) for r in trials])
    return means, ses


def apply_edit(rng, p, delta, sparse=None, headroom=True):
    """Return the candidate's true per-task rates for an edit with mean true effect ``delta``.

    sparse=None   : diffuse. Every task moves by an amount proportional to its headroom (gain) or
                    to its current rate (loss), scaled so the mean change is ~delta.
    sparse=pi     : a random fraction pi of tasks moves, the rest are untouched.
    """
    T = len(p)
    if delta == 0:
        return p.copy()
    if sparse is None:
        w = (1 - p) if delta > 0 else p
        w = w / max(w.mean(), 1e-9)
        d = delta * w
    else:
        k = max(1, int(round(sparse * T)))
        w = (1 - p) if delta > 0 else p
        pr = w + 1e-3
        idx = rng.choice(T, size=k, replace=False, p=pr / pr.sum())
        d = np.zeros(T)
        d[idx] = delta * T / k * (w[idx] / max(w[idx].mean(), 1e-9))
    return np.clip(p + d, 0.0, 1.0)


# ----------------------------------------------------------------------------- gate wrappers
def paired_decide(par_means, cand_means, *, k_se, coverage=1.0, min_coverage=0.6, floor=0.0,
                  deltas=None):
    """Run the REAL ``gate.decide`` in ``paired`` mode exactly as harness.py:3019 calls it."""
    d = list(cand_means - par_means) if deltas is None else list(deltas)
    return gate.decide(float(np.mean(par_means)), float(np.mean(cand_means)), split="val",
                       mode="paired", k_se=k_se, paired_deltas=d, paired_se_floor=floor,
                       coverage=coverage, min_coverage=min_coverage)


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
    procs = procs or min(48, os.cpu_count() or 4)
    with mp.get_context("fork").Pool(procs) as pool:
        return pool.map(fn, args, chunksize=1)
