"""#665 workstream 4: change_type threads from a candidate's ``step``/``accept``/
``reject`` event (and, when absent there, graph.jsonl) through reduce_run() onto the
dashboard node — optional/nullable so a run that never recorded one still renders.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _mk_run(tmp: Path, *, events):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.25}, "best_id": "seed"}), encoding="utf-8")
    return rd


_EVENTS = [
    {"kind": "splits", "train": 2, "val": 2, "test": 2, "seed": 0},
    {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25, "cost_usd": 0.0},
    {"kind": "baseline", "val": 0.25, "stderr": 0.0},
    {"kind": "step", "candidate": "cand_a", "accept": True, "reason": "prompt tweak",
     "val": 0.6, "parent": "seed", "parent_val": 0.25, "change_type": "PROMPT_EDIT"},
    {"kind": "step", "candidate": "cand_b", "accept": False, "reason": "no change_type here",
     "val": 0.4, "parent": "cand_a", "parent_val": 0.6},
]


def _node(reduced, nid):
    return next(n for n in reduced["graph"]["nodes"] if n["id"] == nid)


def test_change_type_threads_through_from_the_step_event():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp, events=_EVENTS))
    assert _node(reduced, "cand_a")["change_type"] == "PROMPT_EDIT"


def test_change_type_absent_renders_fine_old_runs_without_it():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp, events=_EVENTS))
    node = _node(reduced, "cand_b")
    assert "change_type" not in node or node.get("change_type") is None


def test_change_type_falls_back_to_graph_jsonl_when_the_event_lacks_it():
    """A candidate recorded via graph.jsonl's append_node (change_type as an **extra
    kwarg, same mechanism commit.py uses via harness.record_iteration) still gets the
    courtesy copy even when the reconstructed events-based node has none."""
    from cap_evolve import RunDir, Budget, dashboard
    from cap_evolve import graph as graph_mod
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text(
        "\n".join(json.dumps(e) for e in [
            {"kind": "splits", "train": 2, "val": 2, "test": 2, "seed": 0},
            {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25, "cost_usd": 0.0},
            {"kind": "baseline", "val": 0.25, "stderr": 0.0},
            {"kind": "step", "candidate": "cand_c", "accept": True, "reason": "ok",
             "val": 0.6, "parent": "seed", "parent_val": 0.25},
        ]) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.25}, "best_id": "seed"}), encoding="utf-8")
    graph_mod.append_node(rd, node_id="cand_c", parents=["seed"], status="accepted",
                          val_mean=0.6, change_type="VALIDATOR_ADD")
    reduced = dashboard.reduce_run(rd)
    assert _node(reduced, "cand_c")["change_type"] == "VALIDATOR_ADD"
