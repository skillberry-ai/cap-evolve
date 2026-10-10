"""Lineage: merge-base, self-parent guard, locked append, --parent, driver lock (#714)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from cap_evolve import Budget, RunDir, graph, lineage
from cap_evolve.candidate_graph import CandidateGraph

ROOT = Path(__file__).resolve().parents[2]


def _rd(tmp_path):
    return RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))


def _add(rd, nid, parents, status="accepted"):
    return graph.append_node(rd, node_id=nid, parents=parents, status=status)


def test_merge_base_of_two_branches_is_their_fork_point(tmp_path):
    rd = _rd(tmp_path)
    _add(rd, "c1", ["seed"])
    _add(rd, "pay", ["c1"])
    _add(rd, "tr", ["c1"])
    _add(rd, "tr2", ["tr"])
    g = CandidateGraph.load(rd)
    assert lineage.merge_base(g, "pay", "tr2") == "c1"
    assert lineage.merge_base(g, "c1", "tr2") == "c1"
    assert sorted(lineage.tips(g)) == ["pay", "tr2"]
    assert lineage.fold_merge_base(g, ["pay"], "tr2") == "c1"


def test_append_refuses_self_parent_and_cycle(tmp_path):
    rd = _rd(tmp_path)
    _add(rd, "a", ["seed"])
    _add(rd, "b", ["a"])
    with pytest.raises(ValueError):
        _add(rd, "a", ["a"])
    with pytest.raises(ValueError):
        _add(rd, "a", ["b"])


def test_legacy_self_parent_row_does_not_break_branches(tmp_path):
    rd = _rd(tmp_path)
    (rd.root / "graph.jsonl").write_text(
        json.dumps({"id": "cand_4", "parents": ["cand_4"], "status": "accepted"}) + "\n"
        + json.dumps({"id": "cand_5", "parents": ["cand_4"], "status": "accepted"}) + "\n")
    assert CandidateGraph.load(rd).branches() == [["cand_4", "cand_5"]]


def test_prepare_candidate_records_parent(tmp_path):
    rd = _rd(tmp_path)
    for t in ("seed", "c1"):
        d = rd.candidate_dir(t)
        d.mkdir(parents=True)
        (d / "f.txt").write_text(t)
    script = ROOT / "skills/algorithms/agent-optimize/scripts/prepare_candidate.py"
    r = subprocess.run([sys.executable, str(script), "-r", str(rd.root), "-t", "x",
                        "--parent", "c1"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (rd.root / "work/x/f.txt").read_text() == "c1"
    assert graph.latest_node(rd, "x")["parents"] == ["c1"]


def test_real_run_self_parent_keeps_lineage(tmp_path):
    # run_20261008_150326: cand_4's accept record lists itself; its earlier records say cand_1.
    import shutil
    rd = _rd(tmp_path)
    shutil.copy(ROOT / "core/tests/fixtures/lineage_self_parent_graph.jsonl", rd.root / "graph.jsonl")
    g = CandidateGraph.load(rd)
    assert g.parents_of("cand_4") == ["cand_1"]
    assert lineage.merge_base(g, "cand_1", "cand_9") == "cand_1"
    assert "cand_1" in lineage.ancestors(g, "cand_9")
    assert "cand_1" not in lineage.tips(g)


def test_merge_base_tie_break_and_fold(tmp_path):
    rd = _rd(tmp_path)
    _add(rd, "x", ["seed"])
    _add(rd, "y", ["seed"])
    _add(rd, "a", ["x", "y"])
    _add(rd, "b", ["x", "y"])
    g = CandidateGraph.load(rd)
    assert lineage.merge_base(g, "a", "b") == "x"
    assert lineage.merge_base(g, "a", "b", score={"y": 0.9, "x": 0.1}) == "y"
    assert lineage.fold_merge_base(g, ["a"], "b") == "x"


def test_legacy_switch_writes_no_proposed_node(tmp_path):
    rd = _rd(tmp_path)
    d = rd.candidate_dir("seed")
    d.mkdir(parents=True)
    (d / "f.txt").write_text("s")
    script = ROOT / "skills/algorithms/agent-optimize/scripts/prepare_candidate.py"
    r = subprocess.run([sys.executable, str(script), "-r", str(rd.root), "-t", "x"],
                       capture_output=True, text=True,
                       env={**os.environ, "CAPEVOLVE_DAG_PARALLEL": "0"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert graph.latest_node(rd, "x") is None


def test_driver_lock_is_exclusive_released_and_steal_overrides(tmp_path):
    lock = tmp_path / "driver.lock"
    host = socket.gethostname()
    lineage.acquire_driver_lock(tmp_path)
    assert json.loads(lock.read_text())["pid"] == os.getpid()
    lineage._release(lock, os.getpid())
    assert not lock.exists()
    lock.write_text(json.dumps({"pid": os.getppid(), "host": host}))
    with pytest.raises(lineage.DriverBusy):
        lineage.acquire_driver_lock(tmp_path)
    lock.write_text(json.dumps({"pid": 1, "host": "elsewhere"}))
    with pytest.raises(lineage.DriverBusy, match="steal-lock"):
        lineage.acquire_driver_lock(tmp_path)
    lineage.acquire_driver_lock(tmp_path, steal=True)
    lineage._release(lock, os.getpid())
    lock.write_text(json.dumps({"pid": 2**22 + 12345, "host": host}))
    lineage.acquire_driver_lock(tmp_path)  # dead pid on this host: replaced
