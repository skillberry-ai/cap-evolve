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


def test_driver_lock_refuses_live_pid_and_steals_dead(tmp_path):
    lock = tmp_path / "driver.lock"
    host = socket.gethostname()
    assert lineage.acquire_driver_lock(tmp_path) is None
    lock.write_text(json.dumps({"pid": os.getppid(), "host": host}))
    assert "refusing" in lineage.acquire_driver_lock(tmp_path)
    lock.write_text(json.dumps({"pid": 2**22 + 12345, "host": host}))
    assert lineage.acquire_driver_lock(tmp_path) is None
