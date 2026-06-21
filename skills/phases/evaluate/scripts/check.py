"""Contract: evaluate aggregates split × trials — it scores exactly the tasks in
the requested split, runs n_trials per task, and reports a mean over them.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Rollout, Score, Task, harness
from cap_evolve.skillcheck import Checker, import_run, temp_run_dir


class _Adapter:
    """Synthetic adapter: reward = 1 on even trials, 0 on odd → mean 0.5 over 2 trials."""

    def tasks(self, split):
        return [Task(id=t, input={}) for t in ("a", "b", "c", "d")]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output=str(seed))

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0 if int(rollout.output) % 2 == 0 else 0.0)

    def materialize(self, candidate_dir):
        return {}


def main() -> int:
    c = Checker("evaluate")
    c.require_main(import_run())

    with tempfile.TemporaryDirectory() as d:
        rd, splits = temp_run_dir(Path(d), ids=("a", "b", "c", "d"), seed=0)
        adapter = _Adapter()
        cand = Path(d) / "cand"
        cand.mkdir()

        res = harness.evaluate_candidate(adapter, cand, run_dir=rd, split="val",
                                         n_trials=2, base_seed=0, tag="chk")
        # only the val split's tasks are scored
        c.check(len(res.per_task) == len(splits.val),
                f"evaluated {len(res.per_task)} tasks, val has {len(splits.val)}",
                note=f"scored exactly the val split ({len(splits.val)} tasks)")
        # 2 trials (seed 0 -> reward 1, seed 1 -> reward 0) average to 0.5 per task
        c.check(all(abs(pt["reward"] - 0.5) < 1e-9 for pt in res.per_task),
                f"per-task mean over trials wrong: {[pt['reward'] for pt in res.per_task]}",
                note="reward is the mean over n_trials per task")
        c.check(all(pt.get("n", 0) == 2 for pt in res.per_task),
                "n_trials not recorded per task")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
