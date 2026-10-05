"""EvaluationPlan construction (issue #665, workstream 2).

Forensic finding this exists for (``run_20261003_184253``): 7 of 8 candidates paid a
full 90-rollout val gate although each targeted <=7 tasks. These tests assert
``build_evaluation_plan`` actually produces a materially smaller affected-task set
than "all of val" for a narrow cluster, and that regression sentinels are present
whenever there is anything to sample them from.
"""

from __future__ import annotations

import json

from cap_evolve import Budget, RunDir
from cap_evolve.evaluation_plan import (
    STAGE_EXPANDED_CLUSTER,
    STAGE_TARGETED_SMALL,
    EvaluationPlan,
    build_evaluation_plan,
    persist_evaluation_plan,
)

#: Stand-in for "all of val" -- a benchmark-sized task universe, to show the plan's
#: affected set is a small fraction of it, not the whole thing.
_ALL_VAL_TASKS = [str(i) for i in range(30)]


def test_narrow_cluster_yields_a_materially_smaller_affected_set_than_all_val():
    cluster = {"signature": "wrong write action", "tasks": ["5", "9", "14"],
               "score_lost": 0.2, "tag": "wrong_write_action"}
    history = {"kept_good": [t for t in _ALL_VAL_TASKS if t not in cluster["tasks"]]}

    plan = build_evaluation_plan(cluster, graph=None, history=history)

    assert plan.affected_tasks == ["14", "5", "9"]
    assert len(plan.affected_tasks) < len(_ALL_VAL_TASKS) / 2  # materially smaller
    assert plan.stage == STAGE_TARGETED_SMALL


def test_regression_sentinels_present_and_disjoint_from_affected(tmp_path):
    cluster = {"signature": "payment method count violation", "tasks": ["8", "20"],
               "score_lost": 0.05}
    history = {"kept_good": _ALL_VAL_TASKS}  # none overlap "8"/"20" by construction below

    plan = build_evaluation_plan(cluster, graph=None, history=history)

    assert len(plan.regression_sentinels) > 0
    assert set(plan.regression_sentinels).isdisjoint(plan.affected_tasks)
    assert plan.rationale  # non-empty, names the counts


def test_no_kept_good_history_yields_no_sentinels_not_a_guess():
    cluster = {"signature": "x", "tasks": ["1"], "score_lost": 0.1}
    plan = build_evaluation_plan(cluster, graph=None, history=None)
    assert plan.regression_sentinels == []
    assert plan.affected_tasks == ["1"]


def test_broad_cluster_escalates_stage():
    cluster = {"signature": "broad surface", "tasks": [str(i) for i in range(15)],
               "score_lost": 0.5}
    plan = build_evaluation_plan(cluster, graph=None, history=None)
    assert plan.stage == STAGE_EXPANDED_CLUSTER


def test_persist_evaluation_plan_writes_alongside_candidate(tmp_path):
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    (run_dir.candidate_dir("cand_1")).mkdir(parents=True, exist_ok=True)
    plan = EvaluationPlan(affected_tasks=["1", "2"], regression_sentinels=["9"],
                          stage=STAGE_TARGETED_SMALL, rationale="test")

    out_path = persist_evaluation_plan(run_dir, "cand_1", plan)

    assert out_path == run_dir.candidate_dir("cand_1") / "evaluation_plan.json"
    assert out_path.is_file()
    roundtrip = EvaluationPlan.from_dict(json.loads(out_path.read_text()))
    assert roundtrip == plan
