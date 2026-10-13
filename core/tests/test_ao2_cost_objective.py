"""AO-2 conductor, second objective: a ``cost`` objective in the spec makes promotion read reward
AND cost per success (policy.mo_verdict). Fake world as in test_ao2_conductor.py; a candidate's
cost per rollout grows with its "heavy" genes, so some reward wins are bought with cost."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402

import conductor  # noqa: E402
import policy  # noqa: E402

COST = {"objectives": [{"name": "reward", "direction": "maximize"}, {"name": "cost", "direction": "minimize"}]}


def test_cost_objective_is_accepted_others_refused():
    assert conductor.Cfg.from_spec(COST).cost_eps == pytest.approx(0.10)
    assert conductor.Cfg.from_spec({**COST, "ao_cost_eps": 0.2}).cost_eps == pytest.approx(0.2)
    assert conductor.Cfg.from_spec({}).cost_eps is None
    assert conductor.Cfg.from_spec({"ao_merge_bar": 0.3}).merge_bar == pytest.approx(0.3)
    with pytest.raises(conductor.Refused):
        conductor.Cfg.from_spec({"objectives": COST["objectives"] + [{"name": "latency", "direction": "minimize"}]})
    with pytest.raises(conductor.Refused):
        conductor.Cfg.from_spec({"objectives": [{"name": "cost", "direction": "maximize"}]})
    with pytest.raises(conductor.Refused, match="P2"):
        conductor.Cfg.from_spec({**COST, "promotion_rule": "P2"})


def test_cost_per_success_and_verdict():
    ref_r = {f"t{i}": [1.0, 0.0] for i in range(10)}
    ref_c = {f"t{i}": [1.0, 1.0] for i in range(10)}
    same = policy.cost_per_success(ref_r, ref_c, ref_r, ref_c)
    assert same["rel"] == pytest.approx(0.0)
    # more reward at the same cost per rollout: cost per success FALLS
    up_r = {t: [1.0, 1.0] for t in ref_r}
    assert policy.cost_per_success(up_r, ref_c, ref_r, ref_c)["rel"] == pytest.approx(-0.5)
    # a cell without a recorded cost is dropped, never free
    gap_r, gap_c = {t: [1.0, 0.0, 1.0] for t in ref_r}, {t: [1.0, 1.0, None] for t in ref_r}
    assert policy.cost_per_success(gap_r, gap_c, ref_r, ref_c)["rel"] == pytest.approx(0.0)

    cps = lambda rel, z: {"n": 10, "rel": rel, "z": z}
    assert policy.mo_verdict(True, 0.1, 0.03, 10, cps(0.05, 1.0), 0.10, 2.0) == (True, "reward")
    assert policy.mo_verdict(True, 0.1, 0.03, 10, cps(0.30, 4.0), 0.10, 2.0) == (False, "cost_regression")
    assert policy.mo_verdict(False, 0.0, 0.02, 10, cps(-0.30, -4.0), 0.10, 2.0) == (True, "cost")
    assert policy.mo_verdict(False, -0.08, 0.02, 10, cps(-0.30, -4.0), 0.10, 2.0) == (False, "no_gain")   # reward worse
    assert policy.mo_verdict(False, 0.0, 0.02, 10, cps(-0.30, -1.0), 0.10, 2.0) == (False, "no_gain")     # cost drop is noise
    assert policy.mo_verdict(False, 0.0, 0.0, 1, cps(-0.5, -5.0), 0.10, 2.0) == (False, "no_gain")    # one reward task
    assert policy.mo_verdict(True, 0.1, 0.03, 10, {"n": 0}, 0.10, 2.0) == (True, "reward_no_cost_data")


def _heavy(gene) -> bool:
    return random.Random(f"heavy:{gene[0]}").random() < 0.5


class CostBackend(F.FakeBackend):
    """Cost per rollout = 1 + 1.5 per heavy gene; node evidence is captured for the assertions."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.evidence: dict[str, dict] = {}

    def costs(self, tag, ids, window):
        c = 1.0 + 1.5 * sum(_heavy(g) for g in self.w.cands[tag]["genes"])
        return {t: [c] * len(v) for t, v in self.rewards(tag, ids, window).items()}

    def node_event(self, tag, status, **kw):
        if kw.get("why") in ("promoted", "confirm_reject", "screen_reject"):
            self.evidence[tag] = kw
        return super().node_event(tag, status, **kw)


def test_conductor_promotes_only_on_reward_and_cost(tmp_path):
    w, _, cfg = F.make(tmp_path, spec={**COST, "max_metric_calls": 4000, "max_candidates": 14, "ao_plateau_n": 99},
                       world_kw={"salt": 3}, rungs=(8, 16), k_prop=2)
    be = CostBackend(w)
    c = F.run_to_done(w, be, cfg)
    champs = [t for t, n in c.st["nodes"].items() if n["status"] in ("champion", "superseded") and t != "seed"]
    assert champs, "something must be promoted"
    for t in champs:
        ev = be.evidence[t]
        assert ev["route"] in ("reward", "cost")
        if ev["route"] == "reward":
            assert ev["cost_per_success_rel"] <= cfg.cost_eps
    routes = {e.get("route") for e in be.evidence.values()}
    assert "cost_regression" in routes, "a reward win bought with cost must be rejected"
