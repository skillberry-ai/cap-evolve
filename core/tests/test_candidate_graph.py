"""CandidateGraph queries against synthetic graph.jsonl fixtures (issue #665, workstream 2).

Builds graph.jsonl via graph.append_node (the real writer) on a bare RunDir, so these
tests exercise the actual on-disk format rather than a hand-rolled dict -- and never
touch gate.py/round.py/screen.py to do it.
"""

from __future__ import annotations

from pathlib import Path

from cap_evolve import Budget, RunDir, graph
from cap_evolve.candidate_graph import CandidateGraph


def _run_dir(tmp_path) -> RunDir:
    return RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))


def _add(run_dir, node_id, parents, status, **extra):
    return graph.append_node(run_dir, node_id=node_id, parents=parents, status=status, **extra)


def test_frontier_excludes_rejected_and_dominated_nodes(tmp_path):
    run_dir = _run_dir(tmp_path)
    # seed -> a (rejected), seed -> b (accepted) -> c (accepted, no children: live tip)
    _add(run_dir, "a", ["seed"], "rejected", val_mean=0.4)
    _add(run_dir, "b", ["seed"], "accepted", val_mean=0.7)
    _add(run_dir, "c", ["b"], "accepted", val_mean=0.8)

    cg = CandidateGraph.load(run_dir)
    # "b" has an active child ("c") so it is dominated, not a frontier tip; "a" is
    # rejected so it is never a frontier tip even with no children; only "c" is live.
    assert cg.frontier() == ["c"]


def test_frontier_includes_multiple_independent_tips(tmp_path):
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["seed"], "accepted", val_mean=0.5)
    _add(run_dir, "b", ["seed"], "screened", val_mean=0.5)
    _add(run_dir, "c", ["seed"], "rejected", val_mean=0.3)

    cg = CandidateGraph.load(run_dir)
    assert cg.frontier() == ["a", "b"]


def test_superseded_leaf_is_not_frontier(tmp_path):
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["seed"], "superseded", note="bytes carried by a merge")
    cg = CandidateGraph.load(run_dir)
    assert cg.frontier() == []


def test_parents_and_children_of(tmp_path):
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["seed"], "accepted")
    _add(run_dir, "b", ["seed"], "accepted")
    _add(run_dir, "merge", ["a", "b"], "accepted")

    cg = CandidateGraph.load(run_dir)
    assert cg.parents_of("merge") == ["a", "b"]
    assert set(cg.children_of("a")) == {"merge"}
    assert set(cg.children_of("b")) == {"merge"}
    assert cg.children_of("merge") == []
    assert cg.parents_of("nope") == []  # unknown id: empty, not an error


def test_is_descendant_single_and_merge_lineage(tmp_path):
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["seed"], "accepted")
    _add(run_dir, "b", ["a"], "accepted")
    _add(run_dir, "c", ["seed"], "accepted")
    _add(run_dir, "merge", ["b", "c"], "accepted")

    cg = CandidateGraph.load(run_dir)
    assert cg.is_descendant("b", "a") is True
    assert cg.is_descendant("merge", "a") is True       # via b
    assert cg.is_descendant("merge", "c") is True        # direct merge parent
    assert cg.is_descendant("a", "b") is False            # wrong direction
    assert cg.is_descendant("a", "a") is False            # not its own descendant
    assert cg.is_descendant("a", "c") is False            # unrelated lineages


def test_branches_one_path_per_frontier_tip(tmp_path):
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["seed"], "accepted")
    _add(run_dir, "b", ["a"], "accepted")   # tip of lineage 1
    _add(run_dir, "c", ["seed"], "accepted")  # tip of lineage 2 (root itself)

    cg = CandidateGraph.load(run_dir)
    branches = {tuple(path) for path in cg.branches()}
    assert branches == {("a", "b"), ("c",)}


def test_branches_raises_on_parent_cycle_instead_of_hanging(tmp_path):
    # A corrupted/hand-edited graph.jsonl could record a parent cycle (a -> b -> a).
    # branches() must detect it via the same `seen`-set guard is_descendant() uses,
    # not loop forever.
    run_dir = _run_dir(tmp_path)
    _add(run_dir, "a", ["b"], "accepted")
    _add(run_dir, "b", ["a"], "accepted")
    _add(run_dir, "c", ["a"], "accepted")  # the only frontier tip; its ancestry hits the cycle

    cg = CandidateGraph.load(run_dir)
    try:
        cg.branches()
    except ValueError:
        pass
    else:
        raise AssertionError("expected branches() to raise on a parent cycle")


def test_load_on_run_with_no_graph_jsonl_is_empty(tmp_path):
    run_dir = _run_dir(tmp_path)
    cg = CandidateGraph.load(run_dir)
    assert len(cg) == 0
    assert cg.frontier() == []
    assert cg.branches() == []
