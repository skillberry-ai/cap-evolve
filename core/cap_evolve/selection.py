"""Parent selection — a registry of pickers (single source of truth).

Algorithms differ in *which* parent they extend each iteration. Rather than each
algorithm re-deriving (and subtly mis-implementing) selection, every strategy
lives here once, as two parallel registries:

  * ``STRATEGIES``: pure DATA describing each strategy — a label, a description,
    and its parameters (name/type/min/max/default). This single declaration drives
    BOTH parameter validation (``validate_strategy``) AND the dashboard's picker UI,
    so they can never drift.
  * ``PICKERS``: the callables. Each is ``picker(candidates, params, rng) ->
    ranked_list`` and returns candidates ranked best-first (the chosen parent is
    ``ranked[0]``; returning the full ranking lets callers inspect alternatives).

``pick(candidates, strategy, seed)`` is the one entry point: it validates the
strategy, builds a seeded RNG (so a selection is reproducible and the seed is
logged), runs the picker, and returns ``(ranked, seed_used)``.

A "candidate" is a dict with at least ``id`` and ``val`` (aggregate val reward) and
optionally ``per_task`` (list of ``{task_id, reward}``) for the Pareto pickers.
Pure stdlib.
"""

from __future__ import annotations

import random
from typing import Callable


# ---- strategy declarations (data: drives validation + dashboard) -----------

STRATEGIES: dict[str, dict] = {
    "best": {
        "label": "Best",
        "description": "Always extend the single highest-val candidate (greedy hill-climb).",
        "params": [],
    },
    "top_k": {
        "label": "Top-k random",
        "description": "Pick uniformly at random among the top-k by val (explore near the top).",
        "params": [
            {"name": "k", "type": "int", "min": 1, "max": 100, "default": 3},
        ],
    },
    "epsilon_greedy": {
        "label": "Epsilon-greedy",
        "description": "With probability epsilon pick a uniformly random candidate, else the best.",
        "params": [
            {"name": "epsilon", "type": "float", "min": 0.0, "max": 1.0, "default": 0.2},
        ],
    },
    "softmax": {
        "label": "Softmax (Boltzmann)",
        "description": "Sample a parent with probability ∝ exp(val/temperature); lower temp ⇒ greedier.",
        "params": [
            {"name": "temperature", "type": "float", "min": 0.01, "max": 10.0, "default": 0.5},
        ],
    },
    "pareto": {
        "label": "Pareto frontier",
        "description": "Pick uniformly among the per-task Pareto-non-dominated candidates (gepa).",
        "params": [],
    },
    "pareto_per_instance": {
        "label": "Pareto per-instance (frequency-weighted)",
        "description": ("GEPA's per-instance frontier: for each task, the candidate(s) that achieve "
                        "the best reward on it form that task's winners; sample a parent weighted by "
                        "how many tasks it wins (a specialist that uniquely tops some tasks is kept)."),
        "params": [],
    },
}


# ---- pickers (callables: candidates, params, rng -> ranked best-first) ------

def _by_val(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=lambda c: c.get("val", 0.0), reverse=True)


def _pick_best(candidates, params, rng) -> list[dict]:
    return _by_val(candidates)


def _pick_top_k(candidates, params, rng) -> list[dict]:
    k = int(params.get("k", 3))
    ranked = _by_val(candidates)
    head = ranked[:max(1, k)]
    chosen = rng.choice(head)
    # Put the sampled parent first, keep the rest of the ranking after it.
    return [chosen] + [c for c in ranked if c is not chosen]


def _pick_epsilon_greedy(candidates, params, rng) -> list[dict]:
    eps = float(params.get("epsilon", 0.2))
    ranked = _by_val(candidates)
    if rng.random() < eps:
        chosen = rng.choice(candidates)
        return [chosen] + [c for c in ranked if c is not chosen]
    return ranked  # exploit: best first


def _pick_softmax(candidates, params, rng) -> list[dict]:
    import math
    temp = max(1e-6, float(params.get("temperature", 0.5)))
    vals = [c.get("val", 0.0) for c in candidates]
    # Shift by max for numerical stability, then Boltzmann weights.
    mx = max(vals)
    weights = [math.exp((v - mx) / temp) for v in vals]
    chosen = rng.choices(candidates, weights=weights, k=1)[0]
    ranked = _by_val(candidates)
    return [chosen] + [c for c in ranked if c is not chosen]


def pareto_frontier(candidates: list[dict]) -> list[dict]:
    """Per-task Pareto frontier (gepa): candidates not dominated on all tasks.

    Each candidate needs ``per_task`` = list of ``{task_id, reward}``. A dominates B
    if A >= B on every task and > on at least one. Candidates without ``per_task``
    fall back to the global best. (This is the same definition the old
    ``loop.pareto_frontier`` used, lifted here so there is ONE implementation.)
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


def _pick_pareto(candidates, params, rng) -> list[dict]:
    front = pareto_frontier(candidates)
    chosen = rng.choice(front)
    rest = [c for c in _by_val(candidates) if c is not chosen]
    return [chosen] + rest


def _instance_win_counts(candidates: list[dict]) -> dict:
    """For each candidate id, how many tasks it (co-)wins (best reward on that task).

    GEPA's per-instance frontier: a candidate that uniquely tops even one task is a
    specialist the aggregate mean would hide. Ties share the win (each top candidate
    gets credit), so robustly-good generalists also accrue counts.
    """
    usable = [c for c in candidates if c.get("per_task")]
    if not usable:
        return {}
    # task_id -> best reward seen
    best_on: dict = {}
    cand_vecs = []
    for c in usable:
        v = {pt["task_id"]: pt.get("reward", 0.0) for pt in c["per_task"]}
        cand_vecs.append((c, v))
        for t, r in v.items():
            if t not in best_on or r > best_on[t]:
                best_on[t] = r
    counts: dict = {}
    eps = 1e-12
    for c, v in cand_vecs:
        wins = sum(1 for t, r in v.items() if r >= best_on[t] - eps)
        counts[c.get("id")] = wins
    return counts


def _pick_pareto_per_instance(candidates, params, rng) -> list[dict]:
    counts = _instance_win_counts(candidates)
    if not counts:
        return _by_val(candidates)
    # Frequency-weighted sample over candidates that win at least one task.
    pool = [c for c in candidates if counts.get(c.get("id"), 0) > 0] or candidates
    weights = [max(1, counts.get(c.get("id"), 0)) for c in pool]
    chosen = rng.choices(pool, weights=weights, k=1)[0]
    # Rank the rest by win-count then val, for inspectability.
    rest = sorted((c for c in candidates if c is not chosen),
                  key=lambda c: (counts.get(c.get("id"), 0), c.get("val", 0.0)), reverse=True)
    return [chosen] + rest


PICKERS: dict[str, Callable] = {
    "best": _pick_best,
    "top_k": _pick_top_k,
    "epsilon_greedy": _pick_epsilon_greedy,
    "softmax": _pick_softmax,
    "pareto": _pick_pareto,
    "pareto_per_instance": _pick_pareto_per_instance,
}


# ---- validation + entry point ---------------------------------------------

def validate_strategy(obj) -> dict:
    """Normalize a strategy spec into ``{"kind": name, "params": {...}}``.

    ``obj`` may be a bare name (``"best"``) or a dict ``{"kind"/"name": ..,
    <param>: ..}``. Unknown params are dropped; declared params are cast to their
    type and range-checked (clamped to [min, max]); missing params take the
    declared default. Raises ``ValueError`` on an unknown strategy.
    """
    if isinstance(obj, str):
        kind, raw = obj, {}
    elif isinstance(obj, dict):
        kind = obj.get("kind") or obj.get("name") or "best"
        raw = {k: v for k, v in obj.items() if k not in ("kind", "name")}
    else:
        raise ValueError(f"strategy must be a name or dict, got {type(obj).__name__}")

    if kind not in STRATEGIES:
        raise ValueError(f"unknown selection strategy: {kind!r} (have {sorted(STRATEGIES)})")

    params: dict = {}
    for spec in STRATEGIES[kind]["params"]:
        name, typ = spec["name"], spec["type"]
        val = raw.get(name, spec["default"])
        try:
            val = int(val) if typ == "int" else float(val) if typ == "float" else val
        except (TypeError, ValueError):
            val = spec["default"]
        if "min" in spec and isinstance(val, (int, float)):
            val = max(spec["min"], val)
        if "max" in spec and isinstance(val, (int, float)):
            val = min(spec["max"], val)
        params[name] = val
    return {"kind": kind, "params": params}


def pick(candidates: list[dict], strategy="best", seed: int = 0) -> tuple[list[dict], int]:
    """Validate ``strategy``, run its picker with a seeded RNG, return ``(ranked, seed)``.

    ``ranked[0]`` is the chosen parent; the rest is the picker's ranking of the
    alternatives. The ``seed`` is returned so the caller can LOG which seed produced
    this selection (reproducibility). Raises ``ValueError`` on empty candidates or an
    unknown strategy.
    """
    if not candidates:
        raise ValueError("no candidates to select from")
    spec = validate_strategy(strategy)
    rng = random.Random(seed)
    ranked = PICKERS[spec["kind"]](candidates, spec["params"], rng)
    return ranked, seed
