"""Per-candidate objectives for ``GET /api/runs/{id}/objectives`` (issue #702).

Computed from the per-trial rollouts with ``cap_evolve.objectives`` (the same estimators the
reward-gated gate uses); when a candidate has no val rollouts the node's recorded v2
``objectives`` / ``vs_parent`` are returned instead. Old runs work: everything comes from
rollouts + the reducer's nodes.
"""
from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

from . import _bootstrap  # noqa: F401
from cap_evolve import RunDir, dashboard, objectives as ob, specfile


def _num(x):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x


def _clean(d):
    return {k: _num(v) if not isinstance(v, (dict, list)) else v for k, v in d.items()}


def _mean(xs):
    xs = [x for x in xs if x is not None and x == x]
    return sum(xs) / len(xs) if xs else None


def _arm(trials, theta):
    by = ob._by_task(trials)
    per = lambda f: [_mean([f(t) for t in ts]) for ts in by.values()]
    ok = [[t for t in ts if t.reward >= theta] for ts in by.values()]
    E = ob.cost_per_success(trials, trials)
    return {"reward": _mean(per(lambda t: t.reward)),
            "cost_overall": _mean(per(lambda t: t.cost_usd)),
            "cost_matched_success": _mean([_mean([t.cost_usd for t in ts]) for ts in ok if ts]),
            "cost_per_success": _num(E.get("E_c")),
            "latency_s": _mean(per(lambda t: None if math.isnan(t.latency_s) else t.latency_s)),
            "n_tasks": len(by), "n_trials": len(trials)}


def _vs(P, C, theta):
    r, m = ob.paired_reward(P, C), ob.matched_cost(P, C, theta)
    e = ob.cost_per_success(P, C)
    lat = ob.metric_delta(P, C, {"name": "latency", "source": "latency", "direction": "min"}, theta)
    return {"reward": {k: _num(r[k]) for k in ("d", "se", "n")} | {"z": _num(r["d"] / r["se"]) if r["se"] else 0.0},
            "cost_matched": {**{k: _num(m.get(k)) for k in ("d", "rel", "se", "z", "coverage")},
                             "n_matched": m["n"], "matched_task_ids": m["tasks"]},
            "ecps": {k: _num(e.get(k)) for k in ("d", "rel", "se", "z")},
            "latency": {k: _num(lat.get(k)) for k in ("d", "rel")}}


_CACHE: dict[str, tuple] = {}
_CACHE_MAX = 8


def _stamp(root: Path, spec_path) -> tuple:
    """Invalidation key: mtimes of the files/dirs a new eval or decision touches."""
    names = [root / "events.jsonl", root / "graph.jsonl", root / "rollouts" / "val", root / "state.json"]
    names += [spec_path] if spec_path else []
    return tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in names)


def run_objectives(run_path: Path) -> dict:
    """Cached per run dir on :func:`_stamp` (LRU of 8); cold cost is dominated by
    ``reduce_run`` plus reading every val rollout once (seconds on a 450MB run)."""
    rd = RunDir.open(Path(run_path))
    spec_path = specfile.resolve_spec_path(rd, dashboard._find_project_dir(rd.root))
    key, stamp = str(rd.root), _stamp(rd.root, spec_path)
    hit = _CACHE.pop(key, None)
    if hit and hit[0] == stamp:
        _CACHE[key] = hit  # re-insert = most recently used
        return hit[1]
    res = _compute(rd, spec_path)
    _CACHE[key] = (stamp, res)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    return res


def _compute(rd, spec_path) -> dict:
    nodes = {n["id"]: n for n in dashboard.reduce_run(rd)["graph"]["nodes"]}
    spec = specfile.spec_for_run(rd, dashboard._find_project_dir(rd.root))
    cfg = ob.cfg_from_spec(spec)
    theta = ob.success_theta(cfg)
    gate_src = ("spec:reward_gated" if (spec.get("reward_gated") or {}) else "GateCfg defaults (no reward_gated in spec)")
    cache: dict[str, list] = {}
    trials = lambda tag: cache.setdefault(tag, ob.load_trials(rd, tag))
    out = {}
    for nid, n in nodes.items():
        C = trials(nid)
        parent = n.get("base_for_eval") or (n.get("parents") or [None])[0]
        row = {"parent": parent, "eval_state": n.get("eval_state"),
               # recorded optimizer spend for this candidate (v2 cost_ledger, else reducer attribution)
               "optimizer_usd": _num((n.get("cost_ledger") or {}).get("optimizer_usd", n.get("opt_cost_usd")))}
        if C:
            row.update(_arm(C, theta))
            P = trials(parent) if parent else []
            row["vs_parent"] = _vs(P, C, theta) if P else n.get("vs_parent")
        else:
            row["vs_parent"] = n.get("vs_parent")
            row["objectives"] = n.get("objectives")
        out[nid] = row
    return {"theta": theta, "gate_cfg_source": gate_src, "gate_cfg": asdict(cfg), "candidates": out}
