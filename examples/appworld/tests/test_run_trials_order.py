"""PR 874 review finding 4: ``run_trials`` waits for the data root before it lints.

Every root read in the adapter goes through ``_wait_readable``. The lint used to run before it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import adapter as adapter_mod  # noqa: E402
from cap_evolve import Task  # noqa: E402


class RunTrialsOrderTests(unittest.TestCase):
    def test_wait_happens_before_the_lint(self):
        calls: list[str] = []
        task = Task(id="aaa1111_1", input={"instruction": "x"})
        with patch.object(adapter_mod, "_search_ids", return_value=[task.id]), \
             patch.object(adapter_mod, "_wait_readable", side_effect=lambda p, *a, **k: calls.append("wait")), \
             patch.object(adapter_mod.lints, "lint_candidate",
                          side_effect=lambda c: calls.append("lint") or ["rejected for the test"]):
            out = adapter_mod.Adapter().run_trials([task], str(EX / "seed_capability"), n_trials=2, base_seed=0)
        self.assertEqual(calls, ["wait", "lint"])
        self.assertEqual([r.output for r in out[task.id]], ["lint_reject", "lint_reject"])


if __name__ == "__main__":
    unittest.main()
