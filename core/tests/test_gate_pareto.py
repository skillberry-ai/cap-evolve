"""``gate_mode: pareto`` — multi-objective acceptance (issue #665, workstream 1).

Covers: dominance correctness (2D/3D), frontier-style accept/reject on
dominated/non-dominated candidates, backward compatibility of the pre-existing
single-metric modes, the cost -> latency -> tokens fallback chain, and the
"no valid secondary metric" refusal.
"""

from __future__ import annotations

import pytest

from cap_evolve import selection
from cap_evolve.gate import ParetoObjectiveError, decide


# ---- selection.dominates: classic 2D/3D dominance cases --------------------

def test_dominates_2d_strictly_better_on_both():
    assert selection.dominates({"a": 2, "b": 2}, {"a": 1, "b": 1})
    assert not selection.dominates({"a": 1, "b": 1}, {"a": 2, "b": 2})


def test_dominates_2d_better_on_one_equal_other():
    assert selection.dominates({"a": 2, "b": 1}, {"a": 1, "b": 1})


def test_dominates_2d_tradeoff_neither_dominates():
    a, b = {"a": 2, "b": 1}, {"a": 1, "b": 2}
    assert not selection.dominates(a, b)
    assert not selection.dominates(b, a)


def test_dominates_identical_is_false():
    assert not selection.dominates({"a": 1, "b": 1}, {"a": 1, "b": 1})


def test_dominates_3d_with_minimize_direction():
    directions = {"reward": "maximize", "cost": "minimize", "latency": "minimize"}
    better = {"reward": 1.0, "cost": 1.0, "latency": 1.0}
    worse = {"reward": 0.5, "cost": 2.0, "latency": 2.0}
    assert selection.dominates(better, worse, directions)
    assert not selection.dominates(worse, better, directions)


def test_dominates_3d_tradeoff_with_minimize_direction():
    directions = {"reward": "maximize", "cost": "minimize"}
    # a wins on reward, loses on cost -> no dominance either way.
    a = {"reward": 1.0, "cost": 2.0}
    b = {"reward": 0.5, "cost": 1.0}
    assert not selection.dominates(a, b, directions)
    assert not selection.dominates(b, a, directions)


# ---- selection.pareto_frontier: frontier maintenance ------------------------

def test_pareto_frontier_drops_dominated_keeps_non_dominated():
    cands = [
        {"id": "c1", "val": 1.0, "per_task": [{"task_id": "t1", "reward": 1.0},
                                               {"task_id": "t2", "reward": 1.0}]},
        {"id": "c2", "val": 0.5, "per_task": [{"task_id": "t1", "reward": 0.0},
                                               {"task_id": "t2", "reward": 0.0}]},
        {"id": "c3", "val": 0.5, "per_task": [{"task_id": "t1", "reward": 1.0},
                                               {"task_id": "t2", "reward": 0.0}]},
    ]
    front_ids = {c["id"] for c in selection.pareto_frontier(cands)}
    # c2 is dominated by c1 on both tasks -> dropped. c3 trades with c1 (loses t2,
    # ties t1) -> wait, c3 ties t1 and loses t2 to c1, so c1 dominates c3 too.
    assert front_ids == {"c1"}


def test_pareto_frontier_keeps_mutual_tradeoff():
    cands = [
        {"id": "c1", "val": 0.5, "per_task": [{"task_id": "t1", "reward": 1.0},
                                               {"task_id": "t2", "reward": 0.0}]},
        {"id": "c2", "val": 0.5, "per_task": [{"task_id": "t1", "reward": 0.0},
                                               {"task_id": "t2", "reward": 1.0}]},
    ]
    front_ids = {c["id"] for c in selection.pareto_frontier(cands)}
    assert front_ids == {"c1", "c2"}


# ---- gate.decide(mode="pareto"): accept/reject on reward+cost -------------

def test_pareto_accept_dominates_on_both_objectives():
    d = decide(0.5, 0.8, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"cost": 1.0}, metrics_current={"cost": 2.0},
               metrics_stderr_candidate={"cost": 0.0}, metrics_stderr_current={"cost": 0.0})
    assert d.accept, d.reason


def test_pareto_reject_dominated_by_current():
    d = decide(0.5, 0.2, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"cost": 2.0}, metrics_current={"cost": 1.0},
               metrics_stderr_candidate={"cost": 0.0}, metrics_stderr_current={"cost": 0.0})
    assert not d.accept, d.reason


def test_pareto_accept_tradeoff_non_dominated():
    # Candidate costs more but reward improves clearly beyond noise -> non-dominated,
    # real win on reward -> accept (this is the "frontier of trade-offs" case).
    d = decide(0.5, 0.9, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"cost": 5.0}, metrics_current={"cost": 1.0},
               metrics_stderr_candidate={"cost": 0.0}, metrics_stderr_current={"cost": 0.0})
    assert d.accept, d.reason


def test_pareto_reject_nominal_only_noise_not_cleared():
    """A nominal reward improvement that cannot clear its own SE, with a nominal cost
    improvement that cannot clear ITS SE either, must not be an accept — the
    significance floor still applies per-objective, not just to reward."""
    d = decide(0.50, 0.51, mode="pareto",
               candidate_stderr=0.2, current_stderr=0.2,
               metrics_candidate={"cost": 0.99}, metrics_current={"cost": 1.0},
               metrics_stderr_candidate={"cost": 0.2}, metrics_stderr_current={"cost": 0.2},
               k_se=1.0)
    assert not d.accept, d.reason


def test_pareto_reject_all_ties_no_real_difference():
    d = decide(0.5, 0.5, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"cost": 1.0}, metrics_current={"cost": 1.0},
               metrics_stderr_candidate={"cost": 0.0}, metrics_stderr_current={"cost": 0.0})
    assert not d.accept, d.reason


# ---- cost -> latency -> tokens fallback chain -------------------------------

def test_pareto_falls_back_to_latency_when_cost_missing():
    d = decide(0.5, 0.8, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"latency": 1.0}, metrics_current={"latency": 2.0},
               metrics_stderr_candidate={"latency": 0.0}, metrics_stderr_current={"latency": 0.0})
    assert d.accept, d.reason
    assert "latency" in d.reason


def test_pareto_falls_back_to_tokens_when_cost_and_latency_missing():
    d = decide(0.5, 0.8, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"tokens": 1.0}, metrics_current={"tokens": 2.0},
               metrics_stderr_candidate={"tokens": 0.0}, metrics_stderr_current={"tokens": 0.0})
    assert d.accept, d.reason
    assert "tokens" in d.reason


def test_pareto_refuses_when_no_secondary_metric_available():
    with pytest.raises(ParetoObjectiveError):
        decide(0.5, 0.8, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={}, metrics_current={})


def test_pareto_refuses_unknown_explicit_objective_without_fallback():
    with pytest.raises(ParetoObjectiveError):
        decide(0.5, 0.8, mode="pareto",
               objectives=[{"name": "reward", "direction": "maximize"},
                           {"name": "memory_mb", "direction": "minimize"}],
               metrics_candidate={}, metrics_current={})


def test_pareto_refuses_noise_accept_when_cost_stderr_missing():
    """Reproduces the review finding: a tie-on-reward candidate with a scalar cost
    delta of pure float noise (no tracked stderr for cost) must NOT be accepted —
    the gate must refuse rather than let the epsilon fallback treat $0.0000001 as a
    real win."""
    with pytest.raises(ParetoObjectiveError):
        decide(0.500, 0.501, mode="pareto",
               candidate_stderr=0.2, current_stderr=0.2,
               metrics_candidate={"cost": 0.9999999}, metrics_current={"cost": 1.0})


def test_pareto_refuses_when_objective_key_missing_from_one_side():
    """``cost`` present only in metrics_candidate (absent from metrics_current) must
    not be read as 0.0 on the missing side — that fabricates a huge fake delta."""
    with pytest.raises(ParetoObjectiveError):
        decide(0.5, 0.5, mode="pareto",
               candidate_stderr=0.0, current_stderr=0.0,
               metrics_candidate={"cost": 1.0}, metrics_current={},
               metrics_stderr_candidate={"cost": 0.0}, metrics_stderr_current={"cost": 0.0})


# ---- backward compatibility: default/old modes unchanged -------------------

def test_default_mode_is_still_significant_single_metric():
    """No gate_mode: pareto anywhere in this call -> identical behaviour to before
    workstream 1 existed."""
    d = decide(0.50, 0.70, candidate_stderr=0.05, current_stderr=0.05)
    assert d.accept
    assert d.reason.startswith("Δ=")  # unchanged reason format, not the pareto one


def test_paired_mode_regression_unchanged():
    d = decide(0.5, 0.6, mode="paired", k_se=1.0,
               paired_deltas=[0.1, 0.1, 0.1, 0.1])
    assert d.accept
    assert "paired" in d.reason
    assert d.threshold == pytest.approx(0.0)  # SE collapses (identical deltas) -> strict fallback


def test_strict_mode_unchanged():
    d = decide(0.5, 0.51, mode="strict")
    assert d.accept
    assert d.reason == "Δ=+0.0100 > 0"
