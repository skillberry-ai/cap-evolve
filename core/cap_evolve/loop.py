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


def _as_k_dict(v) -> dict:
    """{k: value} pass^k/pass@k, tolerating the legacy bare-scalar shape.

    Old run dirs (and ``report/scripts/check.py``) stored ``pass_k`` as a single
    float, which ``dict(...)`` cannot consume (TypeError). Read it as k=1.
    """
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"1": float(v)}
    return {}


def has_valid_trials(pt) -> bool:
    """Did this task produce at least one real measurement?

    ``raw.valid_trials`` is written by the harness as the count of trials whose
    rollout carried NO ``error``. A task at 0 was never actually run (image build
    failure, agent-setup timeout, runner crash), so its reward is missing data
    rather than evidence of failure, and it must stay out of the split mean and
    out of paired deltas.

    Tolerant of shapes that predate the field: older run dirs and hand-built
    Scores have no ``valid_trials``, and for those we fall back to "at least one
    trial did not error", finally defaulting to True so absent metadata can never
    silently erase a task from a mean.
    """
    raw = (pt.get("raw") if isinstance(pt, dict) else getattr(pt, "raw", None)) or {}
    if "valid_trials" in raw:
        return int(raw.get("valid_trials") or 0) > 0
    n = raw.get("n_trials")
    errored = raw.get("errored_trials")
    if n is not None and errored is not None:
        return int(errored) < int(n)
    return True


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
    # Honest denominator: how many of the split's tasks actually produced a
    # measurement. ``reward`` is the mean over ``n_scored`` tasks, NOT over
    # ``n_tasks`` — so a caller can tell "scored 0.08" from "0.08 because two
    # thirds of the split never ran".
    n_tasks: int = 0
    n_scored: int = 0

    @property
    def coverage(self) -> float:
        """Fraction of the split that produced a measurement (1.0 if unknown)."""
        if not self.n_tasks:
            return 1.0
        return self.n_scored / self.n_tasks

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
            "n_tasks": self.n_tasks,
            "n_scored": self.n_scored,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SplitResult":
        return cls(
            split=d.get("split", "val"),
            reward=float(d.get("reward") or 0.0),
            stderr=float(d.get("stderr") or 0.0),
            pass_k=_as_k_dict(d.get("pass_k")),
            pass_at_k=_as_k_dict(d.get("pass_at_k")),
            per_task=list(d.get("per_task") or []),
            cost_usd=float(d.get("cost_usd") or 0.0),
            tokens=int(d.get("tokens") or 0),
            seconds=float(d.get("seconds") or 0.0),
            n_tasks=int(d.get("n_tasks") or 0),
            n_scored=int(d.get("n_scored") or 0),
        )


def aggregate_scores(split: str, scores: Sequence[Score], ks: Sequence[int] = (1, 2)) -> SplitResult:
    """Turn per-task ``Score`` objects into a ``SplitResult`` with honest stats.

    Tasks that produced NO valid trial are excluded from every statistic. They
    are still reported in ``per_task`` (nothing is hidden), but counting their
    0.0 would understate the capability and — worse — hand the optimizer a
    phantom regression to chase. ``n_tasks``/``n_scored`` expose the real
    denominator so callers can refuse to gate on a decimated split.
    """
    scored = [s for s in scores if has_valid_trials(s)]

    means = [s.reward for s in scored]
    ses = [s.stderr for s in scored]
    overall = stats.aggregate(means)
    overall_se = stats.combined_stderr(means, ses)

    # pass^k / pass@k are only DEFINED when every task has at least k trials. With
    # fewer, stats.pass_k returns None (undefined) and stats.pass_at_k silently
    # clamps k → n; emitting either as a reliability number reads as "0% reliable"
    # when the truth is "not enough trials". So we OMIT any k > min trials — a
    # missing key is the N/A representation (JSON: absent/null; human surfaces
    # render "N/A"/"—"). k < 1 is undefined too.
    trials_per_task = [len(s.trial_rewards or [s.reward]) for s in scored]
    max_usable_k = min(trials_per_task) if trials_per_task else 0

    pk: dict = {}
    pak: dict = {}
    for k in ks:
        if k < 1 or k > max_usable_k:
            continue
        rel = [stats.pass_k(s.trial_rewards or [s.reward], k) for s in scored]
        cap = [stats.pass_at_k(s.trial_rewards or [s.reward], k) for s in scored]
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
        per_task=[s.to_dict() for s in scores],   # ALL tasks, including unscored
        n_tasks=len(scores),
        n_scored=len(scored),
    )


# ---- parent selection over a frontier of candidates ------------------------

def select_parent(
    candidates: list[dict],
    strategy: str = "best",
    *,
    rng=None,
    epsilon: float = 0.2,
    k: int = 3,
    seed: int = 0,
) -> dict:
    """Pick a parent candidate to extend.

    ``candidates`` is a list of dicts each with at least ``id`` and ``val`` (and
    optionally ``per_task`` for the Pareto strategies). This now DELEGATES to
    ``selection.pick`` so there is exactly one implementation of each strategy
    (``best`` | ``top_k`` | ``epsilon_greedy`` | ``softmax`` | ``pareto`` |
    ``pareto_per_instance``). Returns the single chosen parent (``ranked[0]``).

    Back-compat: the legacy ``epsilon``/``k`` keyword args are folded into the
    strategy params. A passed ``rng`` is used to derive the selection ``seed`` (so
    existing callers that injected an RNG still get varied draws); otherwise
    ``seed`` is used directly.
    """
    from . import selection

    spec: dict = {"kind": strategy}
    if strategy == "top_k":
        spec["k"] = k
    elif strategy == "epsilon_greedy":
        spec["epsilon"] = epsilon
    if rng is not None:
        # Derive a per-call seed from the injected RNG so repeated calls vary.
        seed = rng.randrange(2 ** 31)
    ranked, _ = selection.pick(candidates, spec, seed=seed)
    return ranked[0]


# Kept as a public alias so any external importer of ``loop.pareto_frontier`` still
# works; the implementation lives in ``selection`` (single source of truth).
def pareto_frontier(candidates: list[dict]) -> list[dict]:
    from . import selection
    return selection.pareto_frontier(candidates)
