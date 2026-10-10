"""Sequential paired posterior decision rule (stdlib port of research/design/sim_eval.py).

Per task i: parent rate p_i ~ Beta(.5+s, .5+n-s) from the pooled ledger; candidate rate
q_i | p_i ~ Beta(k_i p_i, k_i (1-p_i)) updated by the candidate's own trials. D = mean_i(q_i-p_i)
is the val-mean difference over ALL tasks, so tasks nobody sampled widen D instead of tripping a
coverage fraction. Accept iff P(D>DMIN) >= P_ACC; prune iff <= P_REJ (P_REJ_LATE after 100
rollouts) once MIN_USED rollouts are spent; a parent-stable task the candidate collapses on
rejects regardless. Budget exhausted undecided = inconclusive (not accepted).
"""

from __future__ import annotations

import os
import random

DMIN, P_ACC, P_REJ, P_REJ_LATE, MIN_USED = 0.02, 0.95, 0.10, 0.25, 40
K_IMPACT, K_CANARY, K_OTHER = 3.0, 6.0, 12.0
M = 400  # posterior draws


def k_vector(p_par) -> list[float]:
    """Prior strength per task from the parent's rate: flaky/failing tasks are what an edit can
    move (K_IMPACT), stable passes are regression canaries (K_CANARY). ``K_OTHER`` is for tasks a
    caller knows the diff cannot touch (pass a custom k to ``Pair``)."""
    return [K_CANARY if p >= .85 else K_IMPACT for p in p_par]


class Pair:
    """Candidate vs parent, per-task ``(successes, trials)``; ``k`` = per-task prior strength."""

    def __init__(self, k, sp, np_, sc=None, nc=None):
        T = len(k)
        self.k, self.sp, self.np_ = list(k), list(map(float, sp)), list(map(float, np_))
        self.sc = [0.0] * T if sc is None else list(map(float, sc))
        self.nc = [0.0] * T if nc is None else list(map(float, nc))
        self.T = T

    def add(self, arm: int, task: int, reward: float) -> None:
        """arm 0 = candidate, 1 = parent."""
        if arm == 0:
            self.sc[task] += reward; self.nc[task] += 1
        else:
            self.sp[task] += reward; self.np_[task] += 1

    def draw(self, rng: random.Random, m: int = M):
        pp = [[min(.99, max(.01, rng.betavariate(self.sp[i] + .5, self.np_[i] - self.sp[i] + .5)))
               for i in range(self.T)] for _ in range(m)]
        pc = [[rng.betavariate(p[i] * self.k[i] + self.sc[i],
                               (1 - p[i]) * self.k[i] + self.nc[i] - self.sc[i])
               for i in range(self.T)] for p in pp]
        return pp, pc

    def verdict(self, rng: random.Random, used: int, m: int = M) -> dict:
        pp, pc = self.draw(rng, m)
        T = self.T
        D = [sum(c[i] - p[i] for i in range(T)) / T for p, c in zip(pp, pc)]
        p_beat = sum(d > DMIN for d in D) / m
        pm = [(self.sp[i] + .5) / (self.np_[i] + 1) for i in range(T)]
        canary = [i for i in range(T) if pm[i] >= .85 and self.nc[i] >= 3
                  and sum(c[i] - p[i] < -0.25 for p, c in zip(pp, pc)) / m > .9]
        if canary:
            decision = "prune"
        elif p_beat >= P_ACC:
            decision = "accept"
        elif used >= MIN_USED and p_beat <= (P_REJ if used < 100 else P_REJ_LATE):
            decision = "prune"
        else:
            decision = None
        return {"p_beat": p_beat, "decision": decision, "canary_tasks": canary,
                "d_mean": sum(D) / m}


def enabled(spec: dict | None = None) -> bool:
    """`ablation.active_eval`: env CAPEVOLVE_ACTIVE_EVAL wins, then spec ablation.active_eval;
    default OFF until the E2E replay validates it."""
    env = os.environ.get("CAPEVOLVE_ACTIVE_EVAL", "").strip().lower()
    if env:
        return env not in {"0", "false", "no", "off"}
    ab = (spec or {}).get("ablation")
    return bool(ab.get("active_eval")) if isinstance(ab, dict) else False


def from_ledger(run_dir, cand_hash: str, parent_hash: str, task_ids=None, split: str = "val") -> Pair:
    """Pair built from the eval_index ledger (pooled over every tag sharing a hash). Default task
    set = every task either hash has a row for."""
    from . import eval_index
    cc, pc = (eval_index.counts(run_dir, h, split) for h in (cand_hash, parent_hash))
    ids = sorted(set(cc) | set(pc)) if task_ids is None else [str(t) for t in task_ids]
    g = lambda c, t: c.get(t, (0.0, 0))
    sp, np_ = [g(pc, t)[0] for t in ids], [g(pc, t)[1] for t in ids]
    k = k_vector([(s + .5) / (n + 1) for s, n in zip(sp, np_)])
    return Pair(k, sp, np_, [g(cc, t)[0] for t in ids], [g(cc, t)[1] for t in ids])


def summarize(run_dir, cand_tag: str, parent_tag: str, split: str = "val", seed: int = 0) -> dict | None:
    """Posterior read-out for two tags from the ledger (None when either has no rows)."""
    from . import eval_index
    h = [eval_index.cap_hash(run_dir.candidate_dir(t)) for t in (cand_tag, parent_tag)]
    P = from_ledger(run_dir, h[0], h[1], split=split)
    if not P.T or not sum(P.nc) or not sum(P.np_):
        return None
    v = P.verdict(random.Random(seed), int(sum(P.nc)))
    return {**v, "n_cand": int(sum(P.nc)), "n_parent": int(sum(P.np_)), "tasks": P.T}
