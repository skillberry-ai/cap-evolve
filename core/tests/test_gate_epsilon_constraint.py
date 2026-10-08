"""``gate_mode: epsilon_constraint`` — issue #684 item 2.

Haimes, Lasdon & Wismer's (1971) bounded-objective-function method: maximize the primary
objective (reward, via the SAME paired/significant test the other modes use) subject to each
declared ``constraints`` entry (``{"name", "max"}``) staying under its ceiling. Covers:
accept/reject correctness, the adversarial noise case (a constraint that reads nominally
under its ceiling only because of measurement noise must NOT be treated as satisfied — the
same significance discipline as the ``pareto`` mode's per-objective floor), and the missing-
value/missing-stderr refusals.
"""

from __future__ import annotations

import pytest

from cap_evolve.gate import ParetoObjectiveError, decide

CONSTRAINTS = [{"name": "cost", "max": 1.0}]


def test_accepts_when_constraint_cleared_and_reward_improves():
    d = decide(0.5, 0.8, mode="epsilon_constraint", constraints=CONSTRAINTS,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={"cost": 0.5}, metrics_stderr_candidate={"cost": 0.01})
    assert d.accept, d.reason
    assert "epsilon_constraint" in d.reason


def test_rejects_when_constraint_violated_even_though_reward_improves():
    d = decide(0.5, 0.9, mode="epsilon_constraint", constraints=CONSTRAINTS,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={"cost": 2.0}, metrics_stderr_candidate={"cost": 0.01})
    assert not d.accept, d.reason
    assert "not confidently cleared" in d.reason


def test_rejects_noise_level_constraint_satisfaction():
    """A cost that reads NOMINALLY under the ceiling (0.99 < 1.0) but whose own measurement
    noise could plausibly put it over must not be treated as satisfied — reproduces the
    adversarial case from the pareto gate's #667 fix, applied to a hard ceiling instead of a
    pairwise comparison."""
    d = decide(0.5, 0.8, mode="epsilon_constraint", constraints=CONSTRAINTS, k_se=1.0,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={"cost": 0.99}, metrics_stderr_candidate={"cost": 0.5})
    assert not d.accept, d.reason


def test_reward_still_gated_on_real_evidence_not_any_positive_delta():
    """Constraint cleared, but the reward improvement itself cannot clear its own SE —
    epsilon_constraint must still reject (it only ADDS a ceiling check, never removes the
    reward significance test the other modes already apply)."""
    d = decide(0.50, 0.51, mode="epsilon_constraint", constraints=CONSTRAINTS,
               candidate_stderr=0.2, current_stderr=0.2,
               metrics_candidate={"cost": 0.1}, metrics_stderr_candidate={"cost": 0.01})
    assert not d.accept, d.reason


def test_uses_paired_deltas_when_available():
    d = decide(0.5, 0.7, mode="epsilon_constraint", constraints=CONSTRAINTS,
               paired_deltas=[0.2, 0.2, 0.2, 0.2],
               metrics_candidate={"cost": 0.3}, metrics_stderr_candidate={"cost": 0.01})
    assert d.accept, d.reason
    assert "paired" in d.reason


def test_no_constraints_declared_behaves_like_reward_only():
    d = decide(0.5, 0.8, mode="epsilon_constraint", constraints=[],
               candidate_stderr=0.01, current_stderr=0.01)
    assert d.accept, d.reason


def test_refuses_missing_constraint_value():
    with pytest.raises(ParetoObjectiveError):
        decide(0.5, 0.8, mode="epsilon_constraint", constraints=CONSTRAINTS,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={}, metrics_stderr_candidate={})


def test_refuses_missing_constraint_stderr():
    with pytest.raises(ParetoObjectiveError):
        decide(0.5, 0.8, mode="epsilon_constraint", constraints=CONSTRAINTS,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={"cost": 0.5}, metrics_stderr_candidate={})


def test_multiple_constraints_all_must_clear():
    constraints = [{"name": "cost", "max": 1.0}, {"name": "latency", "max": 5.0}]
    d = decide(0.5, 0.8, mode="epsilon_constraint", constraints=constraints,
               candidate_stderr=0.01, current_stderr=0.01,
               metrics_candidate={"cost": 0.5, "latency": 6.0},
               metrics_stderr_candidate={"cost": 0.01, "latency": 0.01})
    assert not d.accept, d.reason
    assert "latency" in d.reason
