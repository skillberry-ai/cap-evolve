"""Run schema v2 emitters and the legacy-run reader (issue #701)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cap_evolve import Budget, RunDir, graph
from cap_evolve import schema_v2 as s2
from cap_evolve.candidate_graph import CandidateGraph


def _rd(tmp_path) -> RunDir:
    return RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))


def _events(rd, kind):
    return [json.loads(line) for line in rd.events_path.read_text().splitlines()
            if json.loads(line)["kind"] == kind]


def test_emit_logs_valid_event_and_warns_on_missing_key(tmp_path):
    rd = _rd(tmp_path)
    assert s2.emit(rd, "candidate_proposed", id="c1", parents=["seed"], branch_id="b0")
    assert not s2.emit(rd, "eval_coverage", tag="c1", split="val")  # no task_ids / trials
    assert not s2.emit(rd, "decision", id="c1", decision="bogus")
    assert _events(rd, "candidate_proposed")[0]["branch_id"] == "b0"
    assert _events(rd, "eval_coverage") == []
    assert [w["of"] for w in _events(rd, "schema_warning")] == ["eval_coverage", "decision"]


def test_eval_state_is_monotone(tmp_path):
    rd = _rd(tmp_path)
    node = {"id": "c1", "parents": ["seed"], "status": "queued"}
    assert s2.advance_eval_state(rd, node, "c1", "screened")
    assert not s2.advance_eval_state(rd, {**node, "eval_state": "full"}, "c1", "partial")
    assert not s2.advance_eval_state(rd, node, "c1", "unevaluated")
    ev = _events(rd, "eval_state")
    assert [(e["from"], e["to"]) for e in ev] == [("unevaluated", "screened")]
    assert s2.coverage_state(["1", "2"], 2, 3) == "full"
    assert s2.coverage_state(["1"], 2, 3) == "partial"


def test_v2_extras_round_trip_through_graph(tmp_path):
    rd = _rd(tmp_path)
    graph.append_node(rd, node_id="c1", parents=["seed", "c0"], status="queued",
                      eval_state="unevaluated", base_for_eval="c0", branch_id="b1",
                      parent_roles={"seed": "donor", "c0": "primary"})
    n = CandidateGraph.load(rd).node_v2("c1")
    assert n["base_for_eval"] == "c0" and n["parent_roles"]["c0"] == "primary"
    assert n["eval_state"] == "unevaluated"


def test_legacy_nodes_normalize():
    full = s2.normalize_node({"id": "a", "parents": ["seed"], "status": "gated", "val_mean": 0.5})
    assert full["eval_state"] == "full" and full["base_for_eval"] == "seed"
    scr = s2.normalize_node({"id": "b", "parents": ["a", "x"], "status": "screened",
                             "val_mean": None, "subset": {"task_ids": ["1", "2"]}})
    assert scr["eval_state"] == "screened"
    assert scr["eval_coverage"]["n_tasks"] == 2 and not scr["eval_coverage"]["full"]
    assert scr["parent_roles"] == {"a": "primary", "x": "donor"}


RECORDED = Path("/Users/osherelhadad/Documents/cap-evo-tau/cap-evolve/.capevolve/run_20261008_150326")


@pytest.mark.skipif(not RECORDED.exists(), reason="recorded run not on this machine")
def test_recorded_v1_run_loads_and_normalizes(tmp_path):
    rd = _rd(tmp_path)
    for f in ("graph.jsonl", "events.jsonl"):
        (rd.root / f).write_bytes((RECORDED / f).read_bytes())
    cg = CandidateGraph.load(rd)
    assert len(cg) >= 10
    states = {nid: cg.node_v2(nid)["eval_state"] for nid in cg._nodes}
    assert set(states.values()) <= set(s2.EVAL_STATES)
    assert all(cg.node_v2(nid)["base_for_eval"] for nid in cg._nodes)
