"""Reward-gated multi-objective decision (issue #711): cost is only comparable on the same job.

The old cost objective was the mean over ALL trials, which is confounded by pass rate (failures
cost ~1.7x passes), so a candidate that gives up early looks cheap and one that solves a bit more
looks cheaper than it is. ``decide_reward_gated`` asks two questions in order:

1. **Reward feasibility** (cost can never buy its way past): paired reward delta ``dR`` with SE
   floored at the measured replicate noise. Clearly worse than ``-m`` -> reject; cannot tell yet
   -> ``indecisive`` (grow trials, NEVER accept); feasible -> stage 2.
2. **Epsilon-constraint ordering** on matched-success cost (tasks both arms solve): reward
   superior -> cost is a constraint (``<= +eps_c`` accept, else TRADE-OFF: archive only, never
   champion); otherwise only a real cost win (``< -delta_c``, z <= -1.65, coverage >= 0.7, cost
   per success not worse) is accepted.

Pure: the only I/O is ``load_trials``. Returns a plain ``RGVerdict``; ``gate.py`` wraps it in a
``GateDecision`` (this module must not import gate, which imports it).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from statistics import NormalDist, stdev

#: reward SE measured between byte-identical replicates on run_20261008_150326 (forensics 04).
NOISE_FLOOR = 0.031
_Z_WIN = 1.65
_ROLES = ("gate", "pareto", "display")
_BASES = ("all", "matched_success", "per_success")


@dataclass
class TrialRec:
    task: str
    k: int
    reward: float
    cost_usd: float
    n_msgs: float = 0.0
    latency_s: float = float("nan")
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"task": self.task, "k": self.k, "reward": self.reward, "cost_usd": self.cost_usd,
                "n_msgs": self.n_msgs, "latency_s": None if math.isnan(self.latency_s) else self.latency_s,
                "extras": dict(self.extras)}

    @classmethod
    def from_dict(cls, d: dict) -> "TrialRec":
        lat = d.get("latency_s")
        return cls(task=str(d["task"]), k=int(d.get("k", 0)), reward=float(d["reward"]),
                   cost_usd=float(d.get("cost_usd") or 0.0), n_msgs=float(d.get("n_msgs") or 0.0),
                   latency_s=float("nan") if lat is None else float(lat),
                   extras=dict(d.get("extras") or {}))


@dataclass
class GateCfg:
    m: float = 0.03            # reward feasibility margin (~1 task of 30)
    alpha: float = 0.2         # feasibility confidence 1-alpha (not superiority)
    k_sup: float = _Z_WIN      # reward-superior bar on dR/SE
    eps_c: float = 0.05        # max relative matched-cost rise for a reward-superior accept
    delta_c: float = 0.03      # min relative matched-cost drop for a cost-win accept
    min_coverage: float = 0.7
    theta: float | None = None  # success bar; None = 0.8 * max observed reward
    noise_floor: float = NOISE_FLOOR


def cfg_from_spec(spec: dict | None) -> GateCfg:
    raw = (spec or {}).get("reward_gated") or {}
    return GateCfg(**{k: v for k, v in raw.items() if k in GateCfg.__dataclass_fields__})


def cost_gating_enabled(spec: dict | None) -> bool:
    """``optimizer.ablation.cost_gating`` (default on). False => the legacy gate mode."""
    return ((((spec or {}).get("optimizer") or {}).get("ablation") or {}).get("cost_gating")) is not False


# ---- loading ---------------------------------------------------------------------------------

def _latency(trace) -> float:
    try:
        ts = [datetime.fromisoformat(x["timestamp"]) for x in trace if x.get("timestamp")]
        return (max(ts) - min(ts)).total_seconds() if len(ts) > 1 else float("nan")
    except (ValueError, TypeError):
        return float("nan")


def load_trials(run_dir, tags, split: str = "val") -> list[TrialRec]:
    """Per-trial records from ``rollouts/<split>/<task>__<tag>__t<k>.json``, POOLED over ``tags``
    (byte-identical replicates are one arm). Errored trials are skipped, as in
    ``harness.split_result_from_rollouts``."""
    tags = [tags] if isinstance(tags, str) else list(tags)
    vdir = run_dir.rollouts / split
    out: list[TrialRec] = []
    if not vdir.exists():
        return out
    for tag in tags:
        for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            sc, ro = rec.get("score") or {}, rec.get("rollout") or {}
            if ro.get("error") or (sc.get("raw") or {}).get("errored"):
                continue
            metrics = {m["name"]: m["value"] for m in sc.get("metrics") or []
                       if isinstance(m, dict) and "name" in m}
            tid = str(sc.get("task_id") or f.name.split("__")[0])
            k = int(f.stem.rsplit("__t", 1)[1]) if "__t" in f.stem else 0
            out.append(TrialRec(
                task=tid, k=k, reward=float(sc.get("reward", 0.0)),
                cost_usd=float(ro.get("cost_usd") or 0.0),
                n_msgs=float(metrics.get("num_messages", len(ro.get("trace") or []))),
                latency_s=_latency(ro.get("trace") or []), extras=metrics))
    return out


# ---- estimators ------------------------------------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs)


def _se(xs) -> float:
    return stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")


def _by_task(trials) -> dict[str, list[TrialRec]]:
    out: dict[str, list[TrialRec]] = {}
    for t in trials:
        out.setdefault(t.task, []).append(t)
    return out


def _z(d: float, se: float) -> float:
    return d / se if se and se == se else 0.0


def success_theta(cfg: GateCfg, *arms) -> float:
    if cfg.theta is not None:
        return cfg.theta
    return 0.8 * max([t.reward for a in arms for t in a] or [1.0])


def paired_reward(P, C, noise_floor: float = NOISE_FLOOR) -> dict:
    """``dR = mean_i(R_i^c - R_i^p)`` over tasks in both arms; SE across tasks floored at the
    replicate noise."""
    p, c = _by_task(P), _by_task(C)
    ts = sorted(set(p) & set(c))
    d = [_mean([t.reward for t in c[i]]) - _mean([t.reward for t in p[i]]) for i in ts]
    if not d:
        return {"d": 0.0, "se": noise_floor, "se_raw": float("nan"), "n": 0}
    se = _se(d)
    return {"d": _mean(d), "se_raw": se, "se": max(0.0 if se != se else se, noise_floor), "n": len(d)}


def matched_cost(P, C, theta: float, value=lambda t: t.cost_usd) -> dict:
    """Cost on tasks with >=1 passing trial in BOTH arms (``C_i`` = mean over passing trials).
    ``strict`` repeats it on tasks where EVERY trial passes in both (sensitivity)."""
    p, c = _by_task(P), _by_task(C)
    passing = lambda trs: [value(t) for t in trs if t.reward >= theta and value(t) is not None]
    parent_pass = [i for i in p if passing(p[i])]
    M = sorted(i for i in parent_pass if i in c and passing(c[i]))
    out = _paired_stat([_mean(passing(p[i])) for i in M], [_mean(passing(c[i])) for i in M])
    out.update(tasks=M, coverage=len(M) / len(parent_pass) if parent_pass else 0.0)
    allpass = lambda trs: all(t.reward >= theta for t in trs)
    S = [i for i in M if allpass(p[i]) and allpass(c[i])]
    strict = _paired_stat([_mean([value(t) for t in p[i]]) for i in S],
                          [_mean([value(t) for t in c[i]]) for i in S])
    out["strict"] = strict
    out["sensitivity_disagree"] = bool(S) and strict["n"] > 1 and (strict["d"] > 0) != (out["d"] > 0)
    return out


def _paired_stat(x, y) -> dict:
    n = len(x)
    if not n:
        return {"n": 0, "d": 0.0, "rel": 0.0, "se": float("nan"), "z": 0.0}
    d = [b - a for a, b in zip(x, y)]
    ma = _mean(x)
    se = _se(d)
    return {"n": n, "mean_p": ma, "mean_c": _mean(y), "d": _mean(d), "rel": _mean(d) / ma if ma else 0.0,
            "se": se, "se_rel": se / ma if ma else float("nan"), "z": _z(_mean(d), se)}


def _ratio(arm, tasks, value):
    """Ratio estimator ``sum value / sum reward`` with per-task (cluster) influence values."""
    g = _by_task(arm)
    c = [_mean([value(t) for t in g[i]]) for i in tasks]
    r = [_mean([t.reward for t in g[i]]) for i in tasks]
    rb = _mean(r)
    if rb <= 0:
        return float("inf"), [0.0] * len(tasks)
    E = sum(c) / sum(r)
    return E, [(ci - E * ri) / rb for ci, ri in zip(c, r)]


def cost_per_success(P, C, value=lambda t: t.cost_usd) -> dict:
    """``E = sum cost / sum reward`` (partial credit falls out), paired delta-method CI. A cheap
    failure cuts numerator AND denominator, so E does not reward it."""
    ts = sorted(set(_by_task(P)) & set(_by_task(C)))
    if not ts:
        return {"n": 0, "d": 0.0, "rel": 0.0, "se": float("nan"), "z": 0.0}
    Ep, up = _ratio(P, ts, value)
    Ec, uc = _ratio(C, ts, value)
    if math.isinf(Ep) or math.isinf(Ec):
        worse = math.isinf(Ec) and not math.isinf(Ep)
        return {"n": len(ts), "E_p": Ep, "E_c": Ec, "d": float("inf") if worse else 0.0, "rel": 0.0,
                "se": float("nan"), "z": 99.0 if worse else 0.0}
    se = _se([b - a for a, b in zip(up, uc)])
    return {"n": len(ts), "E_p": Ep, "E_c": Ec, "d": Ec - Ep, "rel": (Ec - Ep) / Ep if Ep else 0.0,
            "se": se, "z": _z(Ec - Ep, se)}


# ---- plug-in metrics -------------------------------------------------------------------------

def _value_fn(spec: dict):
    src = spec.get("source", "cost_usd")
    if src == "cost_usd":
        return lambda t: t.cost_usd
    if src == "latency":
        return lambda t: None if math.isnan(t.latency_s) else t.latency_s
    key = src.split(":", 1)[1] if src.startswith("metric:") else spec["name"]
    return lambda t: t.extras.get(key)


def _validate(objs):
    out = []
    for o in objs or []:
        if o.get("role") is None:
            continue  # legacy pareto/epsilon entries (reward, cost, ...) carry no role
        if o.get("direction") not in ("min", "max", "minimize", "maximize"):
            raise ValueError(f"reward_gated objective {o.get('name')!r}: unknown direction "
                             f"{o.get('direction')!r} (expected min|max)")
        if o["role"] not in _ROLES:
            raise ValueError(f"reward_gated objective {o.get('name')!r}: unknown role {o['role']!r}")
        if o.get("basis", "all") not in _BASES:
            raise ValueError(f"reward_gated objective {o.get('name')!r}: unknown basis {o['basis']!r}")
        out.append(o)
    return out


def metric_delta(P, C, spec: dict, theta: float) -> dict:
    """Parent->candidate delta of one plug-in metric, sign-adjusted so ``worse > 0`` always
    means the candidate got worse in the declared direction."""
    f = _value_fn(spec)
    basis = spec.get("basis", "all")
    keep = lambda arm: [t for t in arm if f(t) is not None]
    P, C = keep(P), keep(C)
    if basis == "matched_success":
        r = matched_cost(P, C, theta, f)
    elif basis == "per_success":
        r = cost_per_success(P, C, f)
    else:
        p, c = _by_task(P), _by_task(C)
        ts = sorted(set(p) & set(c))
        r = _paired_stat([_mean([f(t) for t in p[i]]) for i in ts], [_mean([f(t) for t in c[i]]) for i in ts])
    lower_better = spec["direction"] in ("min", "minimize")
    sign = 1.0 if lower_better else -1.0
    r["worse"] = sign * r["d"]
    r["worse_rel"] = sign * r["rel"]
    r["worse_z"] = sign * r["z"]
    return r


# ---- the decision ----------------------------------------------------------------------------

@dataclass
class RGVerdict:
    outcome: str            # accept | reject | indecisive | tradeoff
    reason: str
    delta: float            # dR
    evidence: dict

    @property
    def accept(self) -> bool:
        return self.outcome == "accept"


def decide_reward_gated(P, C, objectives=None, cfg: GateCfg | None = None) -> RGVerdict:
    cfg = cfg or GateCfg()
    objs = _validate(objectives)
    za = NormalDist().inv_cdf(1 - cfg.alpha)
    theta = success_theta(cfg, P, C)
    R = paired_reward(P, C, cfg.noise_floor)
    d, se = R["d"], R["se"]
    # Both tests are on (dR + m)/SE. (The design text wrote (dR - m) for infeasible, which would
    # reject a byte-identical candidate sitting at the 0.031 noise floor.)
    zf = (d + cfg.m) / se
    ev: dict = {"reward": {**R, "z_feasible": zf, "z_superior": d / se}, "theta": theta,
                "displays": {}}

    def out(outcome, reason, stage="ordering"):
        ev["stage"] = stage
        return RGVerdict(outcome, reason, d, ev)

    M = matched_cost(P, C, theta)
    E = cost_per_success(P, C)
    ev["cost_matched"], ev["ecps"] = M, E
    for o in objs:
        if o["role"] == "display":
            ev["displays"][o["name"]] = metric_delta(P, C, o, theta)

    if zf <= -za:
        return out("reject", f"reward infeasible: dR={d:+.4f} (SE {se:.4f}) is worse than -{cfg.m}"
                             f" at {1 - cfg.alpha:.0%} confidence; cost cannot buy this back", "feasibility")
    if zf < za:
        return out("indecisive", f"reward undetermined: dR={d:+.4f}, z_feasible={zf:.2f} < {za:.2f}"
                                 " -> grow trials, never accept", "feasibility")
    for g in (o for o in objs if o["role"] == "gate"):
        r = ev["displays"][g["name"]] = metric_delta(P, C, g, theta)
        margin = float(g.get("margin", 0.0))
        gse = r["se"] if r["se"] == r["se"] else 0.0
        if ((r["worse"] - margin) / gse >= za) if gse > 0 else (r["worse"] > margin):
            return out("reject", f"gate metric {g['name']} breached margin {margin}: "
                                 f"worse by {r['worse']:+.4g}", "feasibility")

    pareto = [("matched_cost", M, cfg.eps_c)] + [
        (o["name"], ev["displays"].setdefault(o["name"], metric_delta(P, C, o, theta)),
         float(o.get("eps", cfg.eps_c)))
        for o in sorted((o for o in objs if o["role"] == "pareto"), key=lambda o: o.get("order", 0))]
    over = [n for n, r, eps in pareto if _rel(r) > eps]
    if d / se > cfg.k_sup:
        if not over:
            return out("accept", f"reward superior (dR={d:+.4f}, z={d / se:.2f}) and matched cost "
                                 f"{M['rel']:+.1%} within +{cfg.eps_c:.0%}")
        ev["tradeoff"] = True
        return out("tradeoff", f"reward superior but {over} exceed their constraint "
                               f"(matched cost {M['rel']:+.1%}): archive only, not champion")
    win = (M["n"] > 1 and M["rel"] < -cfg.delta_c and M["z"] <= -_Z_WIN
           and M["coverage"] >= cfg.min_coverage and E["z"] < 1 and not over)
    if win:
        return out("accept", f"non-inferior reward and matched cost win {M['rel']:+.1%} "
                             f"(z={M['z']:.2f}, coverage {M['coverage']:.0%})")
    return out("reject", f"no reward gain and no cost win (matched cost {M['rel']:+.1%}, "
                         f"z={M['z']:.2f}, coverage {M['coverage']:.0%}, E z={E['z']:.2f})")


def _rel(r: dict) -> float:
    return r.get("worse_rel", r.get("rel", 0.0)) if r.get("n") else 0.0
