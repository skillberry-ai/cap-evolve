"""Cost-aware acceptance (opt-in): reward first, agent cost second, a clear reward win never rejected.

A search that only maximises reward lets the champion grow without bound: every accepted edit adds prompt
text, skill text and tool output the agent re-reads on every rollout (a hill-climb on a tool-use benchmark
tripled its per-rollout tokens). This module adds an optional second term to ANY accept test of the library
(the P2 confirmation, the P2 cheap accept, the paired gate) without changing how the reward test itself is
computed. Everything is off by default (``cost_lambda: 0``, ``cost_accept: false``).

The cost of a candidate is measured from its OWN rollouts (``Rollout.tokens``: prompt + completion tokens of
the agent under test, or ``cost_usd`` when the adapter reports no tokens), normalised by the incumbent's cost
per rollout on the same stratum: ``rel = cand_cost / ref_cost - 1`` (``+0.5`` = 50% more expensive).

Design (``judge``):

* Reward path. A candidate that passes the reward test is rejected ONLY when its cost-adjusted mean
  ``mean - cost_lambda * max(rel, 0)`` falls below ``dmin`` AND the win is not clear (``z < cost_clear_z``).
  A clear reward win (``z >= cost_clear_z``) is never rejected, whatever it costs: the term is a tie-break
  for marginal wins, not a veto. A cheaper candidate is never penalised.
* Cost path (``cost_accept: true``). A candidate that FAILS the reward test is accepted when reward is
  non-inferior and cost is clearly lower: ``mean - cost_noninf_z * se >= -cost_margin`` and
  ``rel <= -cost_min_saving``. This is how the compress operator (``hc2_compress_every`` /
  ``ao_compress_every``) lands a shorter champion that is no worse.
* Ranking. Among several accepted candidates the champion maximises ``mean - cost_lambda * rel``.
* Missing data (fewer than ``cost_min_n`` priced rollouts on either side) means no cost verdict: the reward
  verdict stands, never a cost accept.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Spec keys read by ``CostParams.from_spec`` (also the list the CLI forwards to a deterministic algorithm).
COST_KEYS = ("cost_lambda", "cost_metric", "cost_clear_z", "cost_accept", "cost_margin", "cost_min_saving",
             "cost_noninf_z", "cost_min_n")
METRICS = ("tokens", "usd")


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class CostParams:
    lam: float = 0.0            # weight of the relative cost increase in the reward path; 0 = off
    metric: str = "tokens"      # tokens (prompt + completion per rollout) | usd
    clear_z: float = 3.0        # a reward win at or above this z is never rejected on cost
    accept: bool = False        # the cost path: non-inferior reward + clearly lower cost is an accept
    margin: float = 0.03        # reward non-inferiority margin of the cost path
    min_saving: float = 0.15    # relative cost reduction the cost path needs
    noninf_z: float = 1.0       # one-sided confidence multiplier of the non-inferiority bound
    min_n: int = 10             # priced rollouts needed on each side for a cost verdict

    @property
    def enabled(self) -> bool:
        return self.lam > 0.0 or self.accept

    @classmethod
    def from_spec(cls, spec: dict | None, *, force_accept: bool = False) -> "CostParams":
        spec = spec or {}
        d = cls()
        # a configured compress operator can only land through the cost path, so it defaults that path on
        # (an explicit ``cost_accept: false`` still wins)
        if "cost_accept" not in spec and (int(spec.get("hc2_compress_every") or 0) > 0
                                          or int(spec.get("hc_compress_every") or 0) > 0
                                          or int(spec.get("ao_compress_every") or 0) > 0):
            force_accept = True
        out = cls(lam=float(spec.get("cost_lambda", d.lam) or 0.0),
                  metric=str(spec.get("cost_metric") or d.metric),
                  clear_z=float(spec.get("cost_clear_z", d.clear_z)),
                  accept=force_accept or _truthy(spec.get("cost_accept", d.accept)),
                  margin=float(spec.get("cost_margin", d.margin)),
                  min_saving=float(spec.get("cost_min_saving", d.min_saving)),
                  noninf_z=float(spec.get("cost_noninf_z", d.noninf_z)),
                  min_n=int(spec.get("cost_min_n", d.min_n)))
        if out.lam < 0 or out.margin < 0 or not 0.0 < out.min_saving < 1.0 or out.min_n < 1 or out.noninf_z < 0:
            raise ValueError("cost_lambda, cost_margin >= 0; cost_min_saving in (0, 1); cost_min_n >= 1")
        if out.metric not in METRICS:
            raise ValueError(f"cost_metric must be one of {METRICS}, got {out.metric!r}")
        return out


@dataclass(frozen=True)
class Judgement:
    accept: bool
    adj: float                  # ranking score: mean - lambda * rel (mean when there is no cost data)
    path: str                   # reward | cost | cost_adjusted | reject | no_cost_data
    reason: str = ""


def per_rollout_costs(rows, metric: str = "tokens") -> list[float]:
    """Cost of each rollout from ledger-style rows (``{"tokens": int, "cost": float|None}``). With the
    ``tokens`` metric a side whose rollouts report no tokens falls back to USD (never to a free 0)."""
    rows = list(rows)
    tok = [float(r.get("tokens") or 0) for r in rows]
    usd = [float(r["cost"]) for r in rows if r.get("cost") is not None]
    if metric == "tokens" and any(t > 0 for t in tok):
        return [t for t in tok if t > 0]
    if metric == "usd" or not any(t > 0 for t in tok):
        return [u for u in usd if u > 0]
    return []


def relative_cost(cand_rows, ref_rows, p: CostParams) -> float | None:
    """``cand_mean_cost / ref_mean_cost - 1``; None when either side has fewer than ``min_n`` priced rollouts
    or the reference costs nothing."""
    c, r = per_rollout_costs(cand_rows, p.metric), per_rollout_costs(ref_rows, p.metric)
    if len(c) < p.min_n or len(r) < p.min_n:
        return None
    rm = sum(r) / len(r)
    if rm <= 0:
        return None
    return (sum(c) / len(c)) / rm - 1.0


def judge(p: CostParams, *, passed: bool, mean: float, se: float, z: float, dmin: float,
          rel: float | None) -> Judgement:
    """Fold the cost term into one reward verdict (see the module docstring for the rule)."""
    if not p.enabled or rel is None:
        return Judgement(passed, mean, "no_cost_data" if p.enabled else "reward")
    adj = mean - p.lam * rel
    if passed:
        penalty = p.lam * max(rel, 0.0)
        if p.lam > 0 and z < p.clear_z and mean - penalty < dmin:
            return Judgement(False, adj, "cost_adjusted",
                             f"cost-adjusted: mean {mean:+.4f} - {p.lam:g} x {max(rel, 0.0):.2f} (relative cost "
                             f"{rel:+.0%}) < dmin {dmin:g}, and z {z:.2f} < {p.clear_z:g} (not a clear win)")
        return Judgement(True, adj, "reward")
    if p.accept and rel <= -p.min_saving:
        bound = mean - p.noninf_z * (se if math.isfinite(se) and se > 0 else 0.0)
        if bound >= -p.margin:
            return Judgement(True, adj, "cost",
                             f"cost win: reward non-inferior (mean {mean:+.4f}, lower bound {bound:+.4f} >= "
                             f"-{p.margin:g}) at {rel:+.0%} relative cost")
    return Judgement(False, adj, "reject")
