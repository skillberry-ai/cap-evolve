"""Contract: diagnose emits a well-formed reflective dataset — carries the actual
task INPUT (not the id), and clusters failures by the normalized-feedback
signature so similar root causes group together.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run, temp_run_dir, write_val_rollout


def main() -> int:
    c = Checker("diagnose")
    run = import_run()
    c.require_main(run)

    with tempfile.TemporaryDirectory() as d:
        rd, _ = temp_run_dir(Path(d))
        # two failures with the SAME root cause but different numbers, one pass.
        write_val_rollout(rd, "a", reward=0.0, feedback="Expected 5 but got 7",
                          task_input={"expr": "2+3"}, output="7")
        write_val_rollout(rd, "b", reward=0.0, feedback="Expected 9 but got 2",
                          task_input={"expr": "4+5"}, output="2")
        write_val_rollout(rd, "c", reward=1.0, feedback="ok",
                          task_input={"expr": "1+1"}, output="2")

        records = run._load_val_records(rd, "seed")
        result = run.diagnose(records, run.normalized_feedback_signature)

        rd_set = result["reflective_dataset"]
        c.check(len(rd_set) == 2, f"expected 2 failing entries, got {len(rd_set)}")
        c.check(result["kept_good"] == ["c"], f"passing task not kept-good: {result['kept_good']}")

        # Inputs must be the real task INPUT, not the task id.
        entry = next(e for e in rd_set if e["task_id"] == "a")
        c.check(entry["Inputs"] == {"expr": "2+3"},
                f"Inputs carries the wrong thing (should be the task input): {entry['Inputs']}",
                note="reflective dataset carries the actual task input")
        c.check(entry["Generated Outputs"] == "7", "Generated Outputs missing the rollout output")

        # the two same-root-cause failures cluster together under one signature.
        c.check(len(result["clusters"]) == 1
                and sorted(result["clusters"][0]["tasks"]) == ["a", "b"],
                f"normalized-feedback clustering did not group same-cause failures: {result['clusters']}",
                note="similar feedback clusters together (not split on first 6 words)")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
