"""Reward-gated multi-objective gate (#711): matched-success cost, cost per success, reward
feasibility, role-tagged plug-in metrics, and the real-run reproduction (cand_1/4/7 NOT accepted
over the seed)."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from cap_evolve import gate, objectives as ob
from cap_evolve.objectives import TrialRec, decide_reward_gated
from cap_evolve.pareto_archive import ArchivePoint, ParetoArchive

FIX = Path(__file__).parent / "fixtures" / "run_20261008_val_trials.json"


def arm(spec, rng=None, extras=None):
    """spec: {task: [(reward, cost), ...]} -> [TrialRec]."""
    return [TrialRec(str(t), k, r, c, 10, 1.0, dict(extras or {}))
            for t, trs in spec.items() for k, (r, c) in enumerate(trs)]


def jitter(rng, c, rel=0.05):
    return c * (1 + rng.uniform(-rel, rel))


# ---- 1. cheap-failure gaming ----------------------------------------------------------------

def test_cheap_failure_gaming_dies_at_stage_1_and_never_enters_matched_set():
    rng = random.Random(1)
    easy, hard = range(22), range(22, 30)
    P = {t: [(1.0, jitter(rng, 10)) for _ in range(4)] for t in easy}
    P.update({t: [(1.0, jitter(rng, 10))] * 3 + [(0.0, jitter(rng, 17))] for t in hard})
    C = {t: [(1.0, jitter(rng, 10)) for _ in range(4)] for t in easy}
    C.update({t: [(0.0, 0.001)] * 4 for t in hard})       # "cannot help" in 3 messages
    P, C = arm(P), arm(C)
    naive = (sum(t.cost_usd for t in C) / len(C)) / (sum(t.cost_usd for t in P) / len(P)) - 1
    assert naive < -0.2                                    # a naive cost objective calls this a win
    v = decide_reward_gated(P, C)
    assert v.outcome == "reject" and v.evidence["stage"] == "feasibility"
    assert v.evidence["reward"]["d"] == pytest.approx(-0.2, abs=0.01)
    assert not set(v.evidence["cost_matched"]["tasks"]) & {str(t) for t in hard}


# ---- 2. shedding within the reward margin ----------------------------------------------------

def _shedding(d_reward):
    """Candidate solves 8 fewer of the expensive parent-solved tasks, buys it back elsewhere."""
    rng = random.Random(2)
    P = {t: [(1.0, 20.0)] * 3 for t in range(12)}          # expensive solved
    P.update({t: [(1.0, 6.0)] * 3 for t in range(12, 24)})
    P.update({t: [(0.0, 8.0)] * 3 for t in range(24, 30)})
    C = {t: [(0.0, 2.0)] * 3 for t in range(4, 12)}        # shed 8 expensive tasks
    C.update({t: [(1.0, 20.0)] * 3 for t in range(4)})
    C.update({t: [(1.0, 5.0)] * 3 for t in range(12, 24)})
    gain = 8 + d_reward * 30                               # solve this many extra new tasks
    for i, t in enumerate(range(24, 30)):
        C[t] = [(min(1.0, max(0.0, gain - i)), 4.0)] * 3
    return arm(P), arm(C)


def test_shedding_expensive_tasks_is_rejected_by_coverage_even_when_overall_cost_drops():
    P, C = _shedding(0.0)
    assert sum(t.cost_usd for t in C) < 0.6 * sum(t.cost_usd for t in P)   # overall far cheaper
    cfg = ob.GateCfg(noise_floor=0.01)
    v = decide_reward_gated(P, C, cfg=cfg)
    assert v.outcome in {"reject", "indecisive"} and not v.accept
    assert v.evidence["cost_matched"]["coverage"] < 0.7


def test_coverage_rule_rejects_at_stage_2_when_reward_is_feasible():
    P, C = _shedding(0.0)
    v = decide_reward_gated(P, C, cfg=ob.GateCfg(noise_floor=0.01, m=0.5))   # reward trivially feasible
    assert v.outcome == "reject" and v.evidence["stage"] == "ordering"
    assert v.evidence["cost_matched"]["coverage"] < 0.7


# ---- 3. identical bytes x200 -----------------------------------------------------------------

def test_identical_bytes_replicates_are_rarely_accepted():
    base = random.Random(3)
    p_pass = [base.choice([0.1, 0.5, 0.9]) for _ in range(30)]
    cost = [base.uniform(5, 15) for _ in range(30)]
    def draw(rng, n=3):
        return arm({t: [((1.0 if rng.random() < p_pass[t] else 0.0), jitter(rng, cost[t], 0.2))
                        for _ in range(n)] for t in range(30)})
    accepted = tradeoff = 0
    for seed in range(200):
        rng = random.Random(seed)
        v = decide_reward_gated(draw(rng), draw(rng))
        accepted += v.accept
        tradeoff += v.outcome == "tradeoff"
    assert accepted / 200 <= 0.1


# ---- 4. reward superior, matched cost +30% => tradeoff ---------------------------------------

def _superior(cost_mult):
    rng = random.Random(4)
    P, C = {}, {}
    for t in range(30):
        c = rng.uniform(8, 12)
        pp = 1.0 if t < 14 else 0.0
        P[t] = [(pp, jitter(rng, c)) for _ in range(3)]
        cp = 1.0 if t < 22 else 0.0                         # solves 8 more tasks (dR = +0.27)
        C[t] = [(cp, jitter(rng, c * cost_mult)) for _ in range(3)]
    return arm(P), arm(C)


def test_reward_superior_but_matched_cost_up_30pct_is_a_tradeoff_not_champion(tmp_path):
    P, C = _superior(1.30)
    v = decide_reward_gated(P, C)
    assert v.outcome == "tradeoff" and not v.accept
    assert v.evidence["tradeoff"] and v.evidence["cost_matched"]["rel"] == pytest.approx(0.30, abs=0.03)
    d = gate.decide(0.0, 0.0, mode="reward_gated", task_records=(P, C))
    assert d.tradeoff and not d.accept and not d.indecisive
    # ... and it still gets an archive slot (archive + ownership only)
    arch = ParetoArchive([{"name": "reward", "direction": "maximize"}])
    ok, _ = arch.try_insert("cand", {"reward": 0.6}, {"reward": 0.0}, per_task=ArchivePoint.per_task_of(C))
    assert ok


def test_reward_superior_with_cheap_matched_cost_is_accepted():
    P, C = _superior(1.02)
    assert decide_reward_gated(P, C).outcome == "accept"


# ---- 5. non-inferior with a real matched cost win --------------------------------------------

def test_noninferior_and_matched_cost_down_12pct_is_accepted():
    rng = random.Random(5)
    P, C = {}, {}
    for t in range(30):
        c = rng.uniform(8, 12)
        r = 1.0 if t < 27 else 0.0                          # 90% coverage of parent successes after 1 loss
        P[t] = [(r, jitter(rng, c)) for _ in range(3)]
        C[t] = [(r, jitter(rng, c * 0.88)) for _ in range(3)]
    v = decide_reward_gated(arm(P), arm(C))
    assert v.outcome == "accept", v.reason
    m = v.evidence["cost_matched"]
    assert m["rel"] == pytest.approx(-0.12, abs=0.02) and m["z"] <= -3 and m["coverage"] >= 0.9


# ---- 6. undetermined --------------------------------------------------------------------------

def test_reward_undetermined_is_indecisive_never_accept():
    # 15 tasks flip 1 -> 0, 14 flip 0 -> 1: dR = -0.033 with a huge SE (cand_7's shape)
    P = arm({t: [((1.0 if t < 15 else 0.0), 10.0)] * 3 for t in range(30)})
    C = arm({t: [((0.0 if t < 15 else (1.0 if t < 29 else 0.0)), 7.0)] * 3 for t in range(30)})
    v = decide_reward_gated(P, C)
    assert v.outcome == "indecisive" and not v.accept
    d = gate.decide(0, 0, mode="reward_gated", task_records=(P, C))
    assert d.indecisive and not d.accept


# ---- 7. partial credit ------------------------------------------------------------------------

def test_partial_credit_trial_counts_in_reward_and_E_but_not_in_matched_set():
    P = arm({"a": [(1.0, 10.0)] * 2, "b": [(0.5, 4.0)] * 2})
    C = arm({"a": [(1.0, 12.0)] * 2, "b": [(0.5, 5.0)] * 2})
    theta = ob.success_theta(ob.GateCfg(), P, C)
    assert theta == pytest.approx(0.8)
    M = ob.matched_cost(P, C, theta)
    assert M["tasks"] == ["a"]                              # the 0.5 task is excluded from M
    assert ob.paired_reward(P, C, 0.0)["n"] == 2            # ...but counted in R
    E = ob.cost_per_success(P, C)
    assert E["E_p"] == pytest.approx((10 + 4) / (1 + 0.5)) and E["E_c"] == pytest.approx((12 + 5) / 1.5)


# ---- 8. plug-in metrics -----------------------------------------------------------------------

def _feasible_cost_win(extra_p, extra_c):
    rng = random.Random(8)
    P, C = {}, {}
    for t in range(30):
        c = rng.uniform(8, 12)
        P[t] = [(1.0, jitter(rng, c)) for _ in range(3)]
        C[t] = [(1.0, jitter(rng, c * 0.85)) for _ in range(3)]
    p, c = arm(P, extras={"tool_errors": extra_p}), arm(C, extras={"tool_errors": extra_c})
    return p, c


def test_display_metric_never_flips_a_verdict_and_gate_metric_breach_rejects():
    P, C = _feasible_cost_win(0.0, 0.5)                     # tool errors up by 0.5
    base = decide_reward_gated(P, C)
    assert base.outcome == "accept"
    spec = {"name": "tool_errors", "source": "metric:tool_errors", "direction": "min"}
    disp = decide_reward_gated(P, C, [{**spec, "role": "display"}])
    assert disp.outcome == base.outcome and disp.evidence["displays"]["tool_errors"]["worse"] > 0
    breach = decide_reward_gated(P, C, [{**spec, "role": "gate", "margin": 0.02}])
    assert breach.outcome == "reject" and "tool_errors" in breach.reason
    ok = decide_reward_gated(P, C, [{**spec, "role": "gate", "margin": 1.0}])
    assert ok.outcome == "accept"


def test_pareto_role_metric_over_its_eps_blocks_an_accept():
    P, C = _feasible_cost_win(1.0, 2.0)                     # +100% on the pareto axis
    spec = {"name": "tool_errors", "source": "metric:tool_errors", "direction": "min", "role": "pareto", "eps": 0.05}
    assert decide_reward_gated(P, C, [spec]).outcome == "reject"


def test_unknown_direction_raises():
    P, C = _feasible_cost_win(0.0, 0.0)
    with pytest.raises(ValueError, match="direction"):
        decide_reward_gated(P, C, [{"name": "x", "role": "gate", "direction": "sideways"}])


# ---- 9. unequal trial counts and the strict-set flag ------------------------------------------

def test_unequal_trial_counts_match_a_manual_computation_and_flag_strict_disagreement():
    # parent: 9 trials/task, candidate: 3 trials/task
    P = arm({"a": [(1.0, 10.0)] * 9, "b": [(1.0, 20.0)] * 6 + [(0.0, 30.0)] * 3, "c": [(1.0, 30.0)] * 9})
    C = arm({"a": [(1.0, 12.0)] * 3, "b": [(1.0, 14.0)] * 3, "c": [(1.0, 33.0)] * 3})
    M = ob.matched_cost(P, C, 1.0)
    # C_i over passing trials: a 10->12, b 20->14, c 30->33 => deltas +2, -6, +3
    assert M["tasks"] == ["a", "b", "c"] and M["n"] == 3
    assert M["d"] == pytest.approx(-1 / 3) and M["mean_p"] == pytest.approx(20.0)
    assert M["rel"] == pytest.approx(-1 / 60)
    sd = math.sqrt(sum((x + 1 / 3) ** 2 for x in (2, -6, 3)) / 2)
    assert M["se"] == pytest.approx(sd / math.sqrt(3))
    # strict set = tasks whose EVERY trial passes in both arms: a and c (b has a parent failure)
    assert M["strict"]["n"] == 2 and M["strict"]["d"] == pytest.approx(2.5)
    assert M["sensitivity_disagree"] is True               # matched says cheaper, strict says dearer


# ---- real run: cand_1 / cand_4 / cand_7 are NOT accepted over the seed -----------------------

@pytest.fixture(scope="module")
def real(tmp_path_factory):
    """Rebuild minimal rollout files from the compact fixture, then read them through load_trials."""
    from cap_evolve import RunDir
    fx = json.loads(FIX.read_text())
    root = tmp_path_factory.mktemp("run")
    class _RD:                                              # load_trials only needs ``.rollouts``
        rollouts = root / "rollouts"
    vdir = _RD.rollouts / "val"
    vdir.mkdir(parents=True)
    for tag, rows in fx.items():
        for task, k, reward, cost, msgs, lat in rows:
            (vdir / f"{task}__{tag}__t{k}.json").write_text(json.dumps({
                "input": task,
                "score": {"task_id": task, "reward": reward,
                          "metrics": [{"name": "num_messages", "value": msgs}]},
                "rollout": {"cost_usd": cost, "trace": [
                    {"timestamp": "2026-10-08T10:00:00"},
                    {"timestamp": f"2026-10-08T10:00:00.{int((lat or 0) * 1000) % 1000:03d}"}]}}))
    seed = ob.load_trials(_RD, ["seed", "ctl_null_i0", "ctl_null_i0r1"])
    return _RD, seed


@pytest.mark.parametrize("tag,rel,z,n,outcome", [
    ("cand_1", 0.170, 4.1, 24, "reject"),
    ("cand_4", 0.143, 3.7, 25, "reject"),
    ("cand_7", 0.151, 2.2, 21, "indecisive"),
])
def test_real_run_candidates_are_not_accepted_over_the_seed(real, tag, rel, z, n, outcome):
    rd, seed = real
    v = decide_reward_gated(seed, ob.load_trials(rd, tag))
    m = v.evidence["cost_matched"]
    assert (m["n"], round(m["rel"], 3), round(m["z"], 1)) == (n, rel, z)
    assert v.outcome == outcome and not v.accept


def test_real_run_cand_7_feasibility_z_is_0_31(real):
    rd, seed = real
    assert decide_reward_gated(seed, ob.load_trials(rd, "cand_7")).evidence["reward"]["z_feasible"] \
        == pytest.approx(0.31, abs=0.01)


def test_real_run_byte_identical_controls_have_no_matched_delta(real):
    rd, _ = real
    a, b = ob.load_trials(rd, "ctl_null_i0"), ob.load_trials(rd, "ctl_null_i0r1")
    m = ob.matched_cost(a, b, 1.0)
    assert abs(m["rel"]) < 0.01 and abs(m["z"]) < 1


# ---- plumbing: gate.decide / ablation / archive ------------------------------------------------

def test_ablation_off_falls_back_to_the_legacy_mode_and_never_enters_reward_gated():
    P, C = _superior(1.30)
    legacy = gate.decide(0.5, 0.6, mode="paired", paired_deltas=[0.1, 0.2, 0.15, 0.1])
    off = gate.decide(0.5, 0.6, mode="reward_gated", cost_gating=False,
                      paired_deltas=[0.1, 0.2, 0.15, 0.1], task_records=(P, C))
    assert off.to_dict() == legacy.to_dict() and off.evidence is None
    with pytest.raises(gate.ParetoObjectiveError):         # on without records: refuses, no aggregate gating
        gate.decide(0.5, 0.6, mode="reward_gated")


def test_legacy_decision_dict_is_unchanged():
    d = gate.decide(0.5, 0.6, mode="paired", paired_deltas=[0.1, 0.2, 0.15]).to_dict()
    assert "evidence" not in d and "tradeoff" not in d


def test_cost_gating_switch_reads_the_spec():
    assert ob.cost_gating_enabled({}) and ob.cost_gating_enabled({"optimizer": {"ablation": {}}})
    assert not ob.cost_gating_enabled({"optimizer": {"ablation": {"cost_gating": False}}})


def test_archive_per_task_survives_save_load_and_supports_pairwise_matched_comparison(tmp_path):
    P, C = _superior(1.30)
    arch = ParetoArchive([{"name": "reward", "direction": "maximize"}])
    arch.points.append(ArchivePoint("parent", {"reward": 0.47}, {"reward": 0.0}, 0, ArchivePoint.per_task_of(P)))
    arch.points.append(ArchivePoint("cand", {"reward": 0.73}, {"reward": 0.0}, 1, ArchivePoint.per_task_of(C)))
    path = tmp_path / "pareto_archive.json"
    arch.save(path)
    back = ParetoArchive.load_or_create(path, arch.objectives)
    parent, cand = back.points
    m = cand.matched_vs(parent)
    assert m["rel"] == pytest.approx(0.30, abs=0.03) and m["n"] == 14
    assert "per_task" not in ArchivePoint("x", {"reward": 1}).to_dict()   # legacy serialisation unchanged
