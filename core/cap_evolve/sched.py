"""Active experiment allocator for the posterior rule (see posterior.py).

Within a candidate/parent pair: greedy variance reduction per rollout (a Gaussian knowledge
gradient: the best next trial is the (arm, task) whose posterior variance drops most), with a
global slot cap. Across sibling candidates: successive-halving stage budgets as the baseline.
"""

from __future__ import annotations

import random

from .posterior import M, P_REJ, P_REJ_LATE, Pair

ROUND = 20                          # rollouts per decision round (both arms interleaved)
STAGES = (40, 100, 270, 450)        # successive-halving cumulative budgets per candidate
CAP_NEW = 270                       # default max new rollouts per candidate


def _bvar(a, b): return a * b / ((a + b) ** 2 * (a + b + 1))


def gains(P: Pair, cap_c, cap_p):
    """Variance reduction of D from one more trial, per task, for the candidate and parent arm."""
    gc, gp = [], []
    for i in range(P.T):
        ap, bp = P.sp[i] + .5, P.np_[i] - P.sp[i] + .5
        pm = ap / (ap + bp)
        ac, bc = pm * P.k[i] + P.sc[i], (1 - pm) * P.k[i] + P.nc[i] - P.sc[i]
        gc.append(_bvar(ac, bc) / (P.nc[i] + P.k[i] + 1) if cap_c[i] > 0 else 0.0)
        gp.append(_bvar(ap, bp) / (P.np_[i] + 2.0) if cap_p[i] > 0 else 0.0)
    return gc, gp


def pick(P: Pair, cap_c, cap_p, n: int = ROUND) -> list[tuple[int, int]]:
    """Next ``n`` (arm, task) rollouts, arm 0 = candidate, 1 = parent. Mutates the remaining-cap
    lists; repeated picks of one task are damped by the diminishing-return factors."""
    gc, gp = gains(P, cap_c, cap_p)
    out = []
    for _ in range(n):
        tc, tp = max(range(P.T), key=gc.__getitem__), max(range(P.T), key=gp.__getitem__)
        if gc[tc] <= 0 and gp[tp] <= 0:
            break
        if gc[tc] >= gp[tp]:
            out.append((0, tc)); cap_c[tc] -= 1
            gc[tc] = gc[tc] * (P.nc[tc] + P.k[tc] + 1) / (P.nc[tc] + P.k[tc] + 2) if cap_c[tc] > 0 else 0.0
        else:
            out.append((1, tp)); cap_p[tp] -= 1
            gp[tp] = gp[tp] * (P.np_[tp] + 2) / (P.np_[tp] + 3) if cap_p[tp] > 0 else 0.0
    return out


def run(P: Pair, draw, cap_c, cap_p, rng: random.Random, cap_new: int = CAP_NEW,
        slots=None, m: int = M):
    """Sequential loop. ``draw(arm, task) -> reward`` runs one rollout. ``slots`` (optional
    one-element list) is a global rollout budget shared across pairs, decremented in place.
    Returns (decision, rollouts_used, last_verdict); decision is accept / prune / inconclusive."""
    cap_c, cap_p = list(map(float, cap_c)), list(map(float, cap_p))
    used, v = 0, {"p_beat": None}
    while used < cap_new:
        n = min(ROUND, cap_new - used, slots[0] if slots else ROUND)
        batch = pick(P, cap_c, cap_p, n) if n > 0 else []
        if not batch:
            break
        for arm, t in batch:
            P.add(arm, t, draw(arm, t))
        used += len(batch)
        if slots:
            slots[0] -= len(batch)
        v = P.verdict(rng, used, m)
        if v["decision"]:
            return v["decision"], used, v
    return "inconclusive", used, v


def halve(p_beats: dict[str, float], used: int) -> list[str]:
    """Successive-halving baseline across siblings: tags not yet pruned by the futility bar at
    this stage budget; the caller funds survivors up to the next ``STAGES`` entry."""
    bar = P_REJ if used < 100 else P_REJ_LATE
    return [t for t, p in p_beats.items() if p > bar]
