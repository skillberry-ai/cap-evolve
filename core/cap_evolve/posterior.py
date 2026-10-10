"""Sequential paired posterior decision rule (stdlib port of research/design/sim_eval.py).

Per task i: parent rate p_i ~ Beta(.5+s, .5+n-s) from the pooled ledger; candidate rate
q_i | p_i ~ Beta(k_i p_i, k_i (1-p_i)) updated by the candidate's own trials. D = mean_i(q_i-p_i)
is the val-mean difference over ALL tasks, so tasks nobody sampled widen D instead of tripping a
coverage fraction. Accept iff P(D>DMIN) >= P_ACC; prune iff <= P_REJ (P_REJ_LATE after 100
rollouts) once MIN_USED rollouts are spent; a parent-stable task the candidate collapses on
rejects regardless. Budget exhausted undecided = inconclusive (not accepted).
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

DMIN, P_ACC, P_REJ, P_REJ_LATE, MIN_USED = 0.02, 0.95, 0.10, 0.25, 40
K_IMPACT, K_CANARY = 3.0, 6.0
STABLE, CANARY_MIN, CANARY_DROP, CANARY_P = .85, 3, 0.3, 0.9  # parent-stable task: >= CANARY_MIN cand trials before any accept
M = 400  # posterior draws


def k_vector(p_par) -> list[float]:
    """Prior strength per task from the parent's rate: flaky/failing tasks are what an edit can
    move (K_IMPACT), stable passes are regression canaries (K_CANARY). A caller that knows which
    tasks the diff cannot touch can pass its own k to ``Pair``."""
    return [K_CANARY if p >= STABLE else K_IMPACT for p in p_par]


class Pair:
    """Candidate vs parent, per-task ``(successes, trials)``; ``k`` = per-task prior strength."""

    def __init__(self, k, sp, np_, sc=None, nc=None):
        T = len(k)
        if not T or not (len(sp) == len(np_) == T):
            raise ValueError("posterior.Pair needs at least one task and equal-length arrays")
        self.k, self.sp, self.np_ = list(k), list(map(float, sp)), list(map(float, np_))
        self.sc = [0.0] * T if sc is None else list(map(float, sc))
        self.nc = [0.0] * T if nc is None else list(map(float, nc))
        self.T = T
        for s_, n_ in list(zip(self.sp, self.np_)) + list(zip(self.sc, self.nc)):
            if not (0 <= s_ <= n_):
                raise ValueError("posterior.Pair: rewards must lie in [0,1] (successes within trials)")

    def stable(self, i: int) -> bool:
        return (self.sp[i] + .5) / (self.np_[i] + 1) >= STABLE

    def uncovered(self) -> list[int]:
        """Parent-stable tasks with fewer than CANARY_MIN candidate trials (accept is blocked)."""
        return [i for i in range(self.T) if self.stable(i) and self.nc[i] < CANARY_MIN]

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
        # canary: flat-prior (evidence-scaled, not k-weighted) P(q_i < p_i - CANARY_DROP)
        canary = [i for i in range(T) if self.stable(i) and self.nc[i] >= CANARY_MIN
                  and sum(rng.betavariate(1 + self.sc[i], 1 + self.nc[i] - self.sc[i]) < p[i] - CANARY_DROP
                          for p in pp) / m > CANARY_P]
        if canary:
            decision = "prune"
        elif p_beat >= P_ACC and not self.uncovered():
            decision = "accept"
        elif used >= MIN_USED and p_beat <= (P_REJ if used < 100 else P_REJ_LATE):
            decision = "prune"
        else:
            decision = None
        return {"p_beat": p_beat, "decision": decision, "canary_tasks": canary,
                "d_mean": sum(D) / m}


def enabled(spec: dict | None = None) -> bool:
    """`optimizer.ablation.active_eval`: env CAPEVOLVE_ACTIVE_EVAL wins, then the spec key;
    default OFF until the E2E replay validates it."""
    env = os.environ.get("CAPEVOLVE_ACTIVE_EVAL", "").strip().lower()
    if env:
        return env not in {"0", "false", "no", "off"}
    opt = (spec or {}).get("optimizer")
    ab = opt.get("ablation") if isinstance(opt, dict) else None
    return bool(ab.get("active_eval")) if isinstance(ab, dict) else False


def from_ledger(run_dir, cand_hash: str, parent_hash: str, task_ids=None, split: str = "val") -> Pair:
    """Pair built from the eval_index ledger (pooled over every tag sharing a hash). Default task
    set = the run's frozen split (so unsampled tasks widen D)."""
    from . import eval_index
    cc, pc = (eval_index.counts(run_dir, h, split) for h in (cand_hash, parent_hash))
    if task_ids is None:  # frozen split: tasks without rows keep full prior uncertainty
        try:
            task_ids = json.loads(Path(run_dir.splits_path).read_text(encoding="utf-8"))[split]
        except (OSError, ValueError, KeyError, TypeError):
            task_ids = sorted(set(cc) | set(pc))
    ids = [str(t) for t in task_ids]
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


def safe_summarize(*a, **kw) -> dict | None:
    """``summarize`` for advisory callers: a malformed ledger yields {"error": ...}, never a crash."""
    try:
        return summarize(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - advisory path must not kill a round
        return {"error": f"{type(exc).__name__}: {exc}"}
