"""task_ownership — per-task best-scorer computation (issue #684 item 3).

Synthetic per-task score dicts only; never touches disk/rollouts (that read path
is ``from_run``, exercised indirectly via plan_round's real-run tests instead).
"""

from __future__ import annotations

from cap_evolve.task_ownership import compute_ownership


def test_single_owner_per_task():
    per_task = {
        "cand_a": {"t1": 1.0, "t2": 0.0},
        "cand_b": {"t1": 0.5, "t2": 1.0},
    }
    out = compute_ownership(per_task)
    assert out["owners"] == {"t1": ["cand_a"], "t2": ["cand_b"]}
    assert out["best_score"] == {"t1": 1.0, "t2": 1.0}
    assert out["ownership_count"] == {"cand_a": 1, "cand_b": 1}


def test_tied_owners_both_recorded():
    per_task = {
        "cand_a": {"t1": 1.0},
        "cand_b": {"t1": 1.0},
        "cand_c": {"t1": 0.2},
    }
    out = compute_ownership(per_task)
    assert out["owners"]["t1"] == ["cand_a", "cand_b"]  # sorted, both tied at the max
    assert out["ownership_count"] == {"cand_a": 1, "cand_b": 1, "cand_c": 0}


def test_candidate_missing_a_task_does_not_compete_for_it():
    per_task = {
        "cand_a": {"t1": 0.3},
        "cand_b": {"t1": 0.9, "t2": 1.0},  # cand_a never evaluated on t2
    }
    out = compute_ownership(per_task)
    assert out["owners"] == {"t1": ["cand_b"], "t2": ["cand_b"]}
    assert out["ownership_count"] == {"cand_a": 0, "cand_b": 2}


def test_champion_dominating_every_task_leaves_others_at_zero_ownership():
    per_task = {
        "champion": {"t1": 1.0, "t2": 1.0, "t3": 1.0},
        "rival": {"t1": 0.5, "t2": 0.4, "t3": 0.1},
    }
    out = compute_ownership(per_task)
    assert all(cids == ["champion"] for cids in out["owners"].values())
    assert out["ownership_count"]["rival"] == 0


def test_empty_input_yields_empty_output():
    out = compute_ownership({})
    assert out == {"owners": {}, "best_score": {}, "ownership_count": {}}
