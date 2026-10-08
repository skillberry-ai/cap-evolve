"""issue #684 item 9: verify the dashboard's Pareto/Tasks views against a REALISTIC
multi-candidate reward+cost fixture — several candidates with genuine dominance
relationships, not just the single-candidate shape #676/#682's own fixture used.

PRs #677/#679/#680/#682/#683 built the Pareto scatter / per-objective Tasks deltas /
timeline graph, but the real run meant to exercise them in `gate_mode: pareto` never
actually ran in that mode (round.py excluded "pareto" from --mode — issue #684 item
1/2, owned elsewhere). This is a SYNTHETIC stand-in for that real archive-shaped data:
cand_a/cand_b are mutually non-dominated (a genuine frontier), cand_c is strictly
worse than cand_a on both axes (a genuine dominated point). It only exercises
`dashboard.reduce_run`'s existing node shape (`val`, `cost_usd`, `per_task`,
`per_task_metrics`) — the same fields #676/#682 already added — and replicates
`dashboard/frontend/src/lib/pareto.ts`'s dominance check in Python so a backend-only
test can prove the data reduce_run hands the frontend actually yields the right
frontier/dominated split (the frontend's own half of this is already covered by
`dashboard/frontend/src/test/pareto.test.ts`).
"""

from __future__ import annotations

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


# Per-candidate (reward, cost) over 2 tasks (t1, t2) — val/cost_usd below are each
# candidate's mean over both. cand_a and cand_b trade off (neither dominates the
# other); cand_c is strictly worse than cand_a on BOTH axes (dominated).
_CANDIDATES = {
    "seed":   {"t1": (0.5, 0.03), "t2": (0.5, 0.03)},
    "cand_a": {"t1": (0.9, 0.01), "t2": (0.6, 0.02)},   # mean reward .75, cost .015 — cheap+good
    "cand_b": {"t1": (1.0, 0.04), "t2": (0.8, 0.05)},   # mean reward .90, cost .045 — pricier, better
    "cand_c": {"t1": (0.6, 0.03), "t2": (0.4, 0.04)},   # mean reward .50, cost .035 — worse AND pricier than cand_a
}


def _mk_run(tmp: Path):
    from cap_evolve import Budget, RunDir

    base = tmp / "base"
    base.mkdir()
    rd = RunDir.create(base, ts="t", budget=Budget())
    # mean cost_usd per candidate, matching _CANDIDATES above — the node's "cost_usd" field
    # (what ParetoScatter plots on the x-axis) comes from the "evaluate" event, not from
    # summing per-task rollouts itself.
    mean_cost = {"seed": 0.03, "cand_a": 0.015, "cand_b": 0.045, "cand_c": 0.035}
    events = [
        {"kind": "splits", "train": 0, "val": 2, "test": 0, "seed": 0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
         "cost_usd": mean_cost["seed"]},
        {"kind": "baseline", "val": 0.5, "stderr": 0.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_a", "reward": 0.75,
         "cost_usd": mean_cost["cand_a"]},
        {"kind": "step", "candidate": "cand_a", "accept": True, "reason": "cheap+good",
         "val": 0.75, "parent": "seed", "parent_val": 0.5},
        {"kind": "evaluate", "split": "val", "tag": "cand_b", "reward": 0.90,
         "cost_usd": mean_cost["cand_b"]},
        {"kind": "step", "candidate": "cand_b", "accept": False, "reason": "pricier tradeoff",
         "val": 0.90, "parent": "seed", "parent_val": 0.5},
        {"kind": "evaluate", "split": "val", "tag": "cand_c", "reward": 0.50,
         "cost_usd": mean_cost["cand_c"]},
        {"kind": "step", "candidate": "cand_c", "accept": False, "reason": "dominated",
         "val": 0.50, "parent": "seed", "parent_val": 0.5},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.5}, "best_id": "seed"}), encoding="utf-8")

    for tag, per_task in _CANDIDATES.items():
        for task, (reward, cost_usd) in per_task.items():
            _write_rollout(rd, "val", task, tag, 0, reward=reward, cost_usd=cost_usd)

    project = base.parent / "project"
    project.mkdir(exist_ok=True)
    (project / "capevolve.yaml").write_text(
        "gate_mode: pareto\n"
        "objectives:\n"
        "  - {name: reward, direction: maximize}\n"
        "  - {name: cost, direction: minimize}\n",
        encoding="utf-8")
    sibling_project = rd.root.parent / "project"
    if sibling_project != project:
        sibling_project.mkdir(exist_ok=True)
        (sibling_project / "capevolve.yaml").write_text(
            (project / "capevolve.yaml").read_text(), encoding="utf-8")
    return rd


def _dominates(a, b):
    """Same rule as dashboard/frontend/src/lib/pareto.ts::paretoFrontier: maximize
    reward, minimize cost; a point dominates another iff it is at least as good on
    both axes and strictly better on at least one."""
    return (a["cost"] <= b["cost"] and a["reward"] >= b["reward"]
            and (a["cost"] < b["cost"] or a["reward"] > b["reward"]))


def _frontier(points: dict) -> set:
    return {pid for pid, p in points.items()
            if not any(_dominates(o, p) for oid, o in points.items() if oid != pid)}


def test_reduce_run_feeds_a_correct_pareto_frontier():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = _mk_run(tmp)
    reduced = dashboard.reduce_run(rd)

    assert reduced["summary"]["objectives"] == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]

    nodes = {n["id"]: n for n in reduced["graph"]["nodes"]}
    for tag in _CANDIDATES:
        assert tag in nodes, f"{tag} missing from the reduced graph"

    # The reducer's own cost_usd/val for each candidate (mean over its per-task rollouts).
    points = {tag: {"reward": nodes[tag]["val"], "cost": nodes[tag]["cost_usd"]}
              for tag in ("cand_a", "cand_b", "cand_c")}
    assert points["cand_a"]["reward"] == 0.75 and round(points["cand_a"]["cost"], 4) == 0.015
    assert points["cand_b"]["reward"] == 0.90 and round(points["cand_b"]["cost"], 4) == 0.045
    assert points["cand_c"]["reward"] == 0.50 and round(points["cand_c"]["cost"], 4) == 0.035

    # cand_a strictly beats cand_c on BOTH axes -> cand_c is dominated, cand_a/cand_b
    # trade off (cand_b wins reward, loses cost) -> both are on the frontier.
    frontier = _frontier(points)
    assert frontier == {"cand_a", "cand_b"}, frontier
    assert "cand_c" not in frontier

    # Tasks tab per-objective deltas: cand_a's own per-task cost vs the seed's, per task.
    seed_metrics = nodes["seed"]["per_task_metrics"]
    cand_a_metrics = nodes["cand_a"]["per_task_metrics"]
    assert seed_metrics["t1"]["cost"] == 0.03 and cand_a_metrics["t1"]["cost"] == 0.01
    assert seed_metrics["t2"]["cost"] == 0.03 and cand_a_metrics["t2"]["cost"] == 0.02
    # ...and per-task reward (the primary objective) is still exactly what was recorded.
    assert nodes["cand_a"]["per_task"] == {"t1": 0.9, "t2": 0.6}
    assert nodes["cand_c"]["per_task"] == {"t1": 0.6, "t2": 0.4}
