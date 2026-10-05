"""plan_round.py's branch-count logic (issue #665, workstream 2).

Forensic finding this exists for: every round of run_20261003_184253 forked exactly
one candidate with no stated reason N was 1, not more. These tests assert the branch
count is a FUNCTION of cluster count/overlap/score_lost -- never a fixed constant (the
anti-pattern issue #665 names explicitly: "Fixed 3-candidate loops").
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan_round  # noqa: E402  (sys.path must be seeded first)


def _cluster(sig: str, tasks: list[str], score_lost: float, tag: str | None = None) -> dict:
    return {"signature": sig, "tasks": tasks, "score_lost": score_lost, "tag": tag}


def test_single_root_cause_yields_one_slot_and_one_ish_branch():
    clusters = [_cluster("wrong write action", ["1", "2"], 0.2)]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert plan_round.estimate_branches(groups[0], groups) == 1


def test_several_unrelated_root_causes_scale_total_branches_up():
    # Four clusters with disjoint vocabularies -> no signature overlap -> 4 slots.
    clusters = [
        _cluster("payment method count violation", ["1"], 0.1),
        _cluster("basic economy change never attempted", ["2"], 0.1),
        _cluster("cancel already flown unenforced", ["3"], 0.1),
        _cluster("origin destination change unenforced", ["4"], 0.1),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 4  # one slot per unrelated cause, not merged

    single_total = plan_round.estimate_branches(
        plan_round.group_clusters([clusters[0]])[0], plan_round.group_clusters([clusters[0]]))
    unrelated_total = sum(plan_round.estimate_branches(g, groups) for g in groups)
    assert unrelated_total > single_total  # proportionally more than the single-cluster case
    assert unrelated_total == 4  # one branch per independent, low-stakes slot


def test_overlapping_root_causes_group_into_fewer_slots_than_unrelated():
    # Four clusters that all share vocabulary ("write action" surface) -> overlap merges
    # them into ONE slot, unlike the unrelated case above which stays at 4 slots.
    clusters = [
        _cluster("wrong write action flight", ["1"], 0.1),
        _cluster("wrong write action payment", ["2"], 0.1),
        _cluster("wrong write action seat", ["3"], 0.1),
        _cluster("wrong write action baggage", ["4"], 0.1),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert len(groups[0]) == 4

    unrelated_groups = plan_round.group_clusters([
        _cluster("payment method count violation", ["1"], 0.1),
        _cluster("basic economy change never attempted", ["2"], 0.1),
        _cluster("cancel already flown unenforced", ["3"], 0.1),
        _cluster("origin destination change unenforced", ["4"], 0.1),
    ])
    assert len(groups) < len(unrelated_groups)  # grouped case: fewer candidate SLOTS


def test_branch_count_is_not_a_fixed_constant():
    """No scenario here may land on a hardcoded "always 3" (or any other fixed N) --
    the count must visibly track the input, both up and down, even against a generous cap.
    """
    one = plan_round.group_clusters([_cluster("a b c", ["1"], 0.1)])
    many_unrelated = plan_round.group_clusters([
        _cluster("alpha", ["1"], 0.1), _cluster("beta", ["2"], 0.1),
        _cluster("gamma", ["3"], 0.1), _cluster("delta", ["4"], 0.1),
        _cluster("epsilon", ["5"], 0.1),
    ])
    high_cap = 100  # a generous ceiling: if the result still came out "3" it would be hardcoded
    n_one = plan_round.estimate_branches(one[0], one, max_cap=high_cap)
    totals_unrelated = sum(plan_round.estimate_branches(g, many_unrelated, max_cap=high_cap)
                          for g in many_unrelated)
    assert n_one == 1
    assert totals_unrelated == 5
    assert n_one != 3 and totals_unrelated != 3  # the exact anti-pattern issue #665 names


def test_high_stakes_single_cluster_slot_gets_a_second_branch():
    """A lone cluster that carries most of the round's score_lost is worth a second
    implementation attempt -- the uncertainty bump, not the cluster-count term."""
    clusters = [
        _cluster("alpha", ["1"], 0.9),   # dominates score_lost
        _cluster("beta", ["2"], 0.05),
        _cluster("gamma", ["3"], 0.05),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 3  # unrelated signatures: no merging
    alpha_group = next(g for g in groups if g[0]["signature"] == "alpha")
    assert plan_round.estimate_branches(alpha_group, groups) == 2  # 1 (count) + 1 (stakes)


def test_max_branches_per_slot_only_clamps_down_never_up():
    clusters = [_cluster(f"shared surface {i}", ["t"], 0.1) for i in range(6)]
    # Make them all overlap (shared "shared surface" tokens) -> one big group of 6.
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert plan_round.estimate_branches(groups[0], groups, max_cap=2) == 2  # clamped down
    assert plan_round.estimate_branches(groups[0], groups, max_cap=100) == 6  # not clamped up to 100
