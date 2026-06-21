"""Contract: intake scaffolds a project from the template and mines reusable
artifacts (task files / capability files) from the working dir before scaffolding.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run, quiet


def main() -> int:
    c = Checker("intake")
    run = import_run()
    c.require_main(run)

    with tempfile.TemporaryDirectory() as d:
        wd = Path(d)
        (wd / "tasks.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")
        cap = wd / "seed" / "prompt.txt"
        cap.parent.mkdir(parents=True)
        cap.write_text("you are an agent", encoding="utf-8")

        found = run.mine_artifacts(wd)
        c.check("tasks.jsonl" in found["task_files"],
                f"did not mine the task file: {found}",
                note="mines existing task files")
        c.check(any(p.endswith("prompt.txt") for p in found["capability_artifacts"]),
                f"did not mine the capability artifact: {found}",
                note="mines existing capability artifacts")

        # scaffold writes the adapter stub + spec under .capevolve/project
        with quiet():
            rc = run.main(["--base", str(wd / ".capevolve"), "--workdir", str(wd)])
        c.check(rc == 0, "intake scaffold returned nonzero")
        proj = wd / ".capevolve" / "project"
        c.check((proj / "adapters" / "adapter.py").exists(),
                "scaffold missing adapters/adapter.py",
                note="scaffolds the adapter stub + spec")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
