"""Run schema v2 emitters and the legacy-run reader (issue #701)."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_eval_state_only_moves_forward(tmp_path):
    rd = _rd(tmp_path)
    node = {"id": "c1", "parents": ["seed"], "status": "proposed"}
    assert s2.advance_eval_state(rd, node, "c1", "screened")
    assert not s2.advance_eval_state(rd, {**node, "eval_state": "full"}, "c1", "partial")
    assert not s2.advance_eval_state(rd, node, "c1", "unevaluated")
    ev = _events(rd, "eval_state")
    assert [(e["from"], e["to"]) for e in ev] == [("unevaluated", "screened")]


def test_coverage_state_ignores_ids_outside_val():
    assert s2.coverage_state(["1", "zzz"], ["1", "2"], 3) == "partial"
    assert s2.coverage_state(["1", "2", "zzz"], ["1", "2"], 3) == "full"
    assert s2.coverage_state(["1", "2"], ["1", "2"], 0, min_trials=1) == "partial"


def test_v2_extras_round_trip_through_graph(tmp_path):
    rd = _rd(tmp_path)
    graph.append_node(rd, node_id="c1", parents=["seed", "c0"], status="proposed",
                      eval_state="unevaluated", base_for_eval="c0", branch_id="b1",
                      parent_roles={"seed": "donor", "c0": "primary"})
    n = CandidateGraph.load(rd).node_v2("c1")
    assert n["base_for_eval"] == "c0" and n["parent_roles"]["c0"] == "primary"
    assert n["eval_state"] == "unevaluated"


def test_legacy_nodes_normalize():
    full = s2.normalize_node({"id": "a", "parents": ["seed"], "status": "gated", "val_mean": 0.5,
                              "gate": {"n": 30}})
    assert full["eval_state"] == "full" and full["base_for_eval"] == "seed"
    scr = s2.normalize_node({"id": "b", "parents": ["a", "x"], "status": "screened",
                             "val_mean": None, "subset": {"task_ids": ["1", "2"]}})
    assert scr["eval_state"] == "screened"
    assert scr["coverage"]["n_tasks"] == 2 and not scr["coverage"]["full"]
    assert scr["parent_roles"] == {"a": "primary", "x": "donor"}


def test_queued_reads_as_proposed_and_self_parent_is_dropped():
    n = s2.normalize_node({"id": "c", "parents": ["c", "p"], "status": "queued"})
    assert n["status"] == "proposed" and n["eval_state"] == "unevaluated"
    assert n["base_for_eval"] == "p" and n["parent_roles"] == {"p": "primary"}


FIX = Path(__file__).parent / "fixtures" / "run_schema_v2"


def _recorded(tmp_path):
    rd = _rd(tmp_path)
    (rd.root / "graph.jsonl").write_bytes((FIX / "graph.jsonl").read_bytes())
    val = json.loads((FIX / "splits.json").read_text())["val"]
    events = [json.loads(line) for line in (FIX / "events.jsonl").read_text().splitlines()]
    return CandidateGraph.load(rd), val, s2.legacy_coverage(events, val)


def test_recorded_run_screen_only_candidate_is_not_full(tmp_path):
    cg, val, evals = _recorded(tmp_path)
    assert len(val) == 30
    c9 = cg.node_v2("cand_9", val_ids=val, evals=evals)  # its val_mean 0.5667 is cand_7's number
    assert c9["eval_state"] == "screened"
    assert c9["coverage"]["n_tasks"] == 8 and c9["coverage"]["n_val_tasks"] == 30
    assert c9["coverage"]["trials_max"] == 1 and c9["coverage"]["full"] is False
    c4 = cg.node_v2("cand_4", val_ids=val, evals=evals)
    assert c4["eval_state"] == "full" and c4["coverage"]["n_tasks"] == 30
    assert c4["coverage"]["trials_min"] == 3


def test_recorded_run_without_events_still_flags_cand_9_screened(tmp_path):
    cg, _, _ = _recorded(tmp_path)
    assert cg.node_v2("cand_9")["eval_state"] == "screened"
    assert cg.node_v2("cand_4")["eval_state"] == "full"


def test_recorded_run_cand_4_base_is_its_real_parent(tmp_path):
    # build_dag's history-aware self-parent fallback (#719) recovers cand_4's real parent.
    cg, val, evals = _recorded(tmp_path)
    assert cg.node_v2("cand_4", val_ids=val, evals=evals).get("base_for_eval") == "cand_1"
