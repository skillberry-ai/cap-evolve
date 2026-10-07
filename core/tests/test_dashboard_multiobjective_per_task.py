"""#676: Tasks tab per-objective per-task scores + delta vs parent (multi-objective runs).

Two things are additive to ``reduce_run``'s shape:

* ``summary["objectives"]`` — the declared ``objectives:``/``gate_mode: pareto`` config
  from the sibling project's ``capevolve.yaml``, ``None`` for an ordinary run.
* ``node["per_task_metrics"]`` — per-task values for every objective besides reward
  (currently just ``cost`` = mean ``cost_usd`` over the task's trials, rebuilt from the
  candidate's persisted rollouts exactly like ``per_task`` reward already is).

Neither key existed before this change; a reader that ignores them sees the exact
shape it always did.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _write_rollout(rd, split, task, tag, trial, *, reward, cost_usd):
    out_dir = rd.rollouts / split
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{task}__{tag}__t{trial}.json").write_text(
        json.dumps({
            "input": None,
            "rollout": {"task_id": task, "cost_usd": cost_usd, "tokens": 0},
            "score": {"task_id": task, "reward": reward, "feedback": ""},
        }),
        encoding="utf-8",
    )


def _mk_run(tmp: Path, *, objectives_block: str | None, gate_mode: str = "pareto"):
    from cap_evolve import Budget, RunDir

    base = tmp / "base"
    base.mkdir()
    rd = RunDir.create(base, ts="t", budget=Budget())
    events = [
        {"kind": "splits", "train": 0, "val": 2, "test": 0, "seed": 0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5, "cost_usd": 0.03},
        {"kind": "baseline", "val": 0.5, "stderr": 0.0},
        {"kind": "step", "candidate": "cand_a", "accept": True, "reason": "cheaper + better",
         "val": 0.75, "parent": "seed", "parent_val": 0.5},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.5}, "best_id": "seed"}), encoding="utf-8")

    # seed: t1 costs $0.02, t2 costs $0.04
    _write_rollout(rd, "val", "t1", "seed", 0, reward=1.0, cost_usd=0.02)
    _write_rollout(rd, "val", "t2", "seed", 0, reward=0.0, cost_usd=0.04)
    # cand_a: t1 unchanged reward but CHEAPER; t2 fixed and cheaper too
    _write_rollout(rd, "val", "t1", "cand_a", 0, reward=1.0, cost_usd=0.01)
    _write_rollout(rd, "val", "t2", "cand_a", 0, reward=1.0, cost_usd=0.02)

    project = base.parent / "project"
    project.mkdir(exist_ok=True)
    spec_lines = [f"gate_mode: {gate_mode}"]
    if objectives_block is not None:
        spec_lines.append(objectives_block)
    (project / "capevolve.yaml").write_text("\n".join(spec_lines) + "\n", encoding="utf-8")
    # RunDir.create nests the run under base/run_<ts>; project must sit beside THAT run
    # dir, matching dashboard.py's `_safe_subpath(root.parent, "project", ...)` lookup.
    sibling_project = rd.root.parent / "project"
    if sibling_project != project:
        sibling_project.mkdir(exist_ok=True)
        (sibling_project / "capevolve.yaml").write_text(
            "\n".join(spec_lines) + "\n", encoding="utf-8")
    return rd


def _node(reduced, nid):
    return next(n for n in reduced["graph"]["nodes"] if n["id"] == nid)


def test_pareto_run_gets_per_task_cost_and_objectives_label():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = _mk_run(tmp, objectives_block=None)  # gate_mode: pareto, no explicit objectives
    reduced = dashboard.reduce_run(rd)

    assert reduced["summary"]["objectives"] == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]

    seed = _node(reduced, "seed")
    assert seed["per_task_metrics"]["t1"]["cost"] == 0.02
    assert seed["per_task_metrics"]["t2"]["cost"] == 0.04

    cand = _node(reduced, "cand_a")
    assert cand["per_task_metrics"]["t1"]["cost"] == 0.01
    assert cand["per_task_metrics"]["t2"]["cost"] == 0.02
    # cand_a's own reward is unchanged by this feature.
    assert cand["per_task"]["t1"] == 1.0
    assert cand["per_task"]["t2"] == 1.0


def test_explicit_objectives_block_is_parsed_from_the_spec():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = _mk_run(
        tmp,
        gate_mode="pareto",
        objectives_block=(
            "objectives:\n"
            "  - {name: reward, direction: maximize}\n"
            "  - {name: cost, direction: minimize}"
        ),
    )
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["objectives"] == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]


def test_single_objective_run_reports_no_objectives():
    """A run with no pareto gate_mode gets ``objectives: None`` — the Tasks tab's cue to
    render exactly as it did before this feature, regardless of what ``per_task_metrics``
    happens to carry (cost is attributed per task unconditionally; the UI gate is
    ``objectives``, not this field's presence)."""
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = _mk_run(tmp, objectives_block=None, gate_mode="paired")
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["objectives"] is None
    # per_task reward is still rebuilt exactly as before.
    assert _node(reduced, "cand_a")["per_task"]["t1"] == 1.0
