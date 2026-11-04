"""PR 874 review finding 3: an episode that raises must not leak gold or paths.

``main()`` used to write ``str(e)`` and the raw traceback into the record. The adapter passed the
message, and a crashed worker's stderr, on to the optimizer's feedback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import aw_agent  # noqa: E402

GOLD = "expected 'GOLD-ANSWER-42'"


def _raise(exc: BaseException):
    try:
        raise exc
    except BaseException as e:  # noqa: BLE001
        return e


class RedactErrorTests(unittest.TestCase):
    def test_evaluate_phase_drops_the_message(self):
        out = aw_agent.redact_error(_raise(AssertionError(GOLD)), "evaluate")
        self.assertNotIn("GOLD-ANSWER", out)
        self.assertTrue(out.startswith("AssertionError during evaluate"))
        self.assertIn("in _raise", out)  # frames are kept

    def test_setup_phase_keeps_a_redacted_capped_message(self):
        e = _raise(FileNotFoundError("/aw/root_opt/data/tasks/x/specs.json key=sk-123 " + "y" * 900))
        out = aw_agent.redact_error(e, "setup", {"/aw/root_opt": "<root>", "sk-123": "<secret>"})
        self.assertIn("<root>/data/tasks", out)
        self.assertNotIn("/aw/root_opt", out)
        self.assertNotIn("sk-123", out)
        self.assertLess(len(out.split(" [")[0]), aw_agent.ERROR_MESSAGE_MAX + 60)

    def test_no_source_lines_in_frames(self):
        out = aw_agent.redact_error(_raise(ValueError("v")), "episode")
        self.assertNotIn("raise exc", out)

    def test_stderr_reduced_to_the_exception_type(self):
        stderr = f'Traceback (most recent call last):\n  File "x.py", line 1\nAssertionError: {GOLD}\n'
        self.assertEqual(aw_agent.redact_stderr(stderr), "AssertionError")
        self.assertEqual(aw_agent.redact_stderr("Killed\n"), "")


class MainRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.spec = self.tmp / "spec.json"
        self.out = self.tmp / "out.json"
        self.spec.write_text(json.dumps({"task_id": "t", "appworld_root": "/aw/root_full", "experiment_name": "e"}))

    def _main_with(self, phase: str, exc: Exception) -> dict:
        def boom(spec):
            aw_agent.set_phase(phase)
            raise exc
        with patch.object(aw_agent, "run_episode", side_effect=boom):
            aw_agent.main(["aw_agent.py", str(self.spec), str(self.out)])
        return json.loads(self.out.read_text())

    def test_record_has_no_traceback_and_no_gold(self):
        rec = self._main_with("evaluate", AssertionError(GOLD))
        self.assertNotIn("traceback", rec)
        self.assertNotIn("GOLD-ANSWER", json.dumps(rec))
        self.assertIn("AssertionError during evaluate", rec["infra_error"])

    def test_root_path_is_replaced(self):
        rec = self._main_with("setup", OSError("cannot open /aw/root_full/data/x"))
        self.assertIn("<root>/data/x", rec["infra_error"])
        self.assertNotIn("/aw/root_full", json.dumps(rec))


class AdapterStderrTests(unittest.TestCase):
    def test_crashed_worker_stderr_does_not_reach_feedback(self):
        import adapter as adapter_mod
        from cap_evolve import Task

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, "", f"Traceback ...\nAssertionError: {GOLD}\n")

        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        ad = adapter_mod.Adapter()
        task = Task(id="t", input={})
        with patch.object(adapter_mod.subprocess, "run", side_effect=fake_run), \
             patch.dict(os.environ, {"AW_INFRA_RETRIES": "0"}):
            r = ad._episode(task, EX / "seed_capability", 0, work, work)
        fb = ad.score(task, r).feedback
        self.assertNotIn("GOLD-ANSWER", r.error + json.dumps(r.metadata) + fb)
        self.assertIn("AssertionError", r.error)


if __name__ == "__main__":
    unittest.main()
