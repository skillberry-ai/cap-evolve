"""Shared optimization-loop helpers, so algorithm ``run.py`` files stay thin.

Algorithm skills differ only in *which* tasks they focus and *how* they select a
parent. The mechanics they all share — evaluate a candidate on a split, gate the
result on val, snapshot/record, pick a parent from the frontier — live here.

This module deliberately holds NO scoring or gating logic of its own; it calls
``stats`` and ``gate`` so the honesty guarantees can't be forked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

from . import stats
from .types import Score


@dataclass
class SplitResult:
    """Aggregate evaluation of one candidate on one split."""

    split: str
    reward: float
    stderr: float
    pass_k: dict = field(default_factory=dict)      # {k: value} pass^k reliability
    pass_at_k: dict = field(default_factory=dict)   # {k: value} pass@k capability
    per_task: list = field(default_factory=list)  # list[Score-as-dict]
    # RUNNER cost of producing this evaluation (summed over rollouts) + wall time
    cost_usd: float = 0.0
    tokens: int = 0
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "split": self.split,
            "reward": self.reward,
            "stderr": self.stderr,
            "pass_k": self.pass_k,
            "pass_at_k": self.pass_at_k,
            "per_task": self.per_task,
            "cost_usd": self.cost_usd,
            "tokens": self.tokens,
            "seconds": self.seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SplitResult":
        return cls(
            split=d.get("split", "val"),
            reward=float(d.get("reward") or 0.0),
            stderr=float(d.get("stderr") or 0.0),
            pass_k=dict(d.get("pass_k") or {}),
            pass_at_k=dict(d.get("pass_at_k") or {}),
            per_task=list(d.get("per_task") or []),
            cost_usd=float(d.get("cost_usd") or 0.0),
            tokens=int(d.get("tokens") or 0),
            seconds=float(d.get("seconds") or 0.0),
        )


def aggregate_scores(split: str, scores: Sequence[Score], ks: Sequence[int] = (1, 2)) -> SplitResult:
    """Turn per-task ``Score`` objects into a ``SplitResult`` with honest stats."""
    means = [s.reward for s in scores]
    ses = [s.stderr for s in scores]
    overall = stats.aggregate(means)
    overall_se = stats.combined_stderr(means, ses)

    pk: dict = {}
    pak: dict = {}
    for k in ks:
        rel = [stats.pass_k(s.trial_rewards or [s.reward], k) for s in scores if (s.trial_rewards or [s.reward])]
        cap = [stats.pass_at_k(s.trial_rewards or [s.reward], k) for s in scores if (s.trial_rewards or [s.reward])]
        if rel:
            pk[str(k)] = stats.mean(rel)      # pass^k: reliability (all k pass)
        if cap:
            pak[str(k)] = stats.mean(cap)     # pass@k: capability (>=1 passes)
    return SplitResult(
        split=split,
        reward=overall,
        stderr=overall_se,
        pass_k=pk,
        pass_at_k=pak,
        per_task=[s.to_dict() for s in scores],
    )


# ---- parent selection over a frontier of candidates ------------------------

def select_parent(
    candidates: list[dict],
    strategy: str = "best",
    *,
    rng=None,
    epsilon: float = 0.2,
    k: int = 3,
) -> dict:
    """Pick a parent candidate to extend.

    ``candidates`` is a list of dicts each with at least ``id`` and ``val``
    (and optionally ``per_task`` for pareto). Strategies mirror evo/gepa:
    ``best`` | ``top_k`` | ``epsilon_greedy`` | ``pareto``.
    """
    if not candidates:
        raise ValueError("no candidates to select from")
    if strategy == "best":
        return max(candidates, key=lambda c: c.get("val", 0.0))
    if strategy == "top_k":
        ranked = sorted(candidates, key=lambda c: c.get("val", 0.0), reverse=True)[:k]
        return (rng or _default_rng()).choice(ranked)
    if strategy == "epsilon_greedy":
        r = (rng or _default_rng())
        if r.random() < epsilon:
            return r.choice(candidates)
        return max(candidates, key=lambda c: c.get("val", 0.0))
    if strategy == "pareto":
        front = pareto_frontier(candidates)
        return (rng or _default_rng()).choice(front)
    raise ValueError(f"unknown selection strategy: {strategy!r}")


def pareto_frontier(candidates: list[dict]) -> list[dict]:
    """Per-task Pareto frontier (gepa): keep candidates not dominated on all tasks.

    Each candidate needs ``per_task`` = list of {task_id, reward}. A candidate A
    dominates B if A >= B on every task and > on at least one. Candidates without
    per_task fall back to the global best.
    """
    usable = [c for c in candidates if c.get("per_task")]
    if not usable:
        return [max(candidates, key=lambda c: c.get("val", 0.0))]

    def vec(c):
        return {pt["task_id"]: pt["reward"] for pt in c["per_task"]}

    vecs = [(c, vec(c)) for c in usable]
    front = []
    for c, cv in vecs:
        dominated = False
        for other, ov in vecs:
            if other is c:
                continue
            keys = set(cv) | set(ov)
            ge_all = all(ov.get(k, 0.0) >= cv.get(k, 0.0) for k in keys)
            gt_any = any(ov.get(k, 0.0) > cv.get(k, 0.0) for k in keys)
            if ge_all and gt_any:
                dominated = True
                break
        if not dominated:
            front.append(c)
    return front or [max(candidates, key=lambda c: c.get("val", 0.0))]


def _default_rng():
    import random
    return random.Random(0)
