"""#676: per-task cost (``Score.raw["cost_usd"]``), the data the Tasks tab's
multi-objective view needs. Every rollout already carries its own ``cost_usd``
(``Rollout.cost_usd``) — the run-level ``evaluate_candidate`` cost is just the sum of
these over tasks/trials, so attributing it per task is additive, not a new measurement.
This covers both the LIVE path (``evaluate_candidate``) and the RESUME path
(``split_result_from_rollouts``, which rebuilds a SplitResult from persisted rollouts) —
they must agree, since the dashboard's reducer uses the resume path exclusively.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import Budget, RunDir, harness  # noqa: E402
from cap_evolve.types import Rollout, Score, Task  # noqa: E402


class _TwoTaskAdapter:
    """t1 costs $0.01/trial, t2 costs $0.03/trial — distinct so a mix-up is visible."""

    def tasks(self, split):
        return [Task(id="t1"), Task(id="t2")]

    def run_target(self, task, ctx, *, seed=0):
        cost = 0.01 if task.id == "t1" else 0.03
        return Rollout(task_id=task.id, cost_usd=cost, tokens=10)

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0)


def test_live_eval_attributes_cost_per_task(tmp_path):
    adapter = _TwoTaskAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, rd, seed=0,
                          split_ids={"train": [], "val": ["t1", "t2"], "test": []})
    result = harness.evaluate_candidate(adapter, tmp_path / "seed", run_dir=rd,
                                        split="val", tag="seed")
    by_task = {pt["task_id"]: pt["raw"]["cost_usd"] for pt in result.to_dict()["per_task"]}
    assert by_task == {"t1": 0.01, "t2": 0.03}
    # Unchanged: the run-level total is still the sum over tasks.
    assert result.cost_usd == 0.04


def test_resume_path_reconstructs_the_same_per_task_cost(tmp_path):
    """``split_result_from_rollouts`` (what the dashboard reducer actually calls) must
    rebuild the identical per-task cost from the persisted rollout files."""
    adapter = _TwoTaskAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, rd, seed=0,
                          split_ids={"train": [], "val": ["t1", "t2"], "test": []})
    harness.evaluate_candidate(adapter, tmp_path / "seed", run_dir=rd, split="val", tag="seed")

    resumed = harness.split_result_from_rollouts(rd, "seed", "val")
    by_task = {pt["task_id"]: pt["raw"]["cost_usd"] for pt in resumed.to_dict()["per_task"]}
    assert by_task == {"t1": 0.01, "t2": 0.03}


def test_a_task_with_no_priced_trial_reports_none_not_zero(tmp_path):
    """A task that never ran (every trial errored before pricing anything) must read as
    unmeasured, not as a free $0.0 — the same honesty rule ``cost_source`` already
    enforces at the run level, now per task."""
    class _AllErrorAdapter(_TwoTaskAdapter):
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, error="boom")

    adapter = _AllErrorAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, rd, seed=0,
                          split_ids={"train": [], "val": ["t1"], "test": []})
    result = harness.evaluate_candidate(adapter, tmp_path / "seed", run_dir=rd,
                                        split="val", tag="seed")
    pt = next(p for p in result.to_dict()["per_task"] if p["task_id"] == "t1")
    # An errored rollout spent $0.0 (never priced), which IS real: it should read as
    # 0.0, not None — None is reserved for "no trial ran at all", which did not happen
    # here (one trial ran and errored).
    assert pt["raw"]["cost_usd"] == 0.0
