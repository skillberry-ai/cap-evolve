"""Contract: finalize scores the test split exactly once (seal-on-success) — a
second finalize on the same run dir raises TestSealError.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Rollout, Score, Task, TestSealError, harness
from cap_evolve.skillcheck import Checker, import_run, temp_run_dir


class _Adapter:
    def tasks(self, split):
        return [Task(id=t, input={}) for t in ("a", "b", "c", "d")]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output="ok")

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0)

    def materialize(self, candidate_dir):
        return {}


def main() -> int:
    c = Checker("finalize")
    c.require_main(import_run())

    with tempfile.TemporaryDirectory() as d:
        rd, _ = temp_run_dir(Path(d), ids=("a", "b", "c", "d"), seed=0)
        adapter = _Adapter()
        best = Path(d) / "best"
        best.mkdir()

        payload = harness.finalize(adapter, run_dir=rd, best_dir=best)
        c.check("test" in payload and payload["test"]["reward"] == 1.0,
                f"finalize did not produce a test result: {payload}",
                note="test scored once on the sealed split")

        try:
            harness.finalize(adapter, run_dir=rd, best_dir=best)
            c.fail("second finalize succeeded — the test seal was not enforced")
        except TestSealError:
            c.note("second finalize refused (test seal enforced)")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
