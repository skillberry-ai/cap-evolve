"""adapters/adapter.py: run_trials, the worker subprocess boundary, and score (README: Harness, Lints)."""

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

# The modules under test live in ../adapters (and ../scripts). `cap_evolve` normally comes
# from the installed package; core/ is a fallback so that
#     python3 benchmarks/appworld/examples/react_agent/tests/test_adapter.py -v
# works from a clean shell, as in benchmarks/parsec/examples/rca_prompts/tests. Appended, not prepended: a second copy of
# cap_evolve ahead of the installed one would be worse than an awkward invocation.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "adapters"))
sys.path.append(str(Path(__file__).resolve().parents[5] / "core"))

import adapter as adapter_mod  # noqa: E402
from cap_evolve import Rollout, Task  # noqa: E402

KEY = adapter_mod.aw_agent.KEY_ENV
GOLD = "expected 'GOLD-ANSWER-42'"


class TestScore(unittest.TestCase):
    def setUp(self):
        self.ad, self.Rollout = adapter_mod.Adapter(), Rollout
        self.task = Task(id="t", input={"instruction": "x"})

    def test_success_and_failure_feedback(self):
        ok = self.Rollout(task_id="t", metadata={"success": True, "num_tests": 2, "pass_count": 2, "n_steps": 4})
        bad = self.Rollout(task_id="t", metadata={"success": False, "num_tests": 2, "pass_count": 1, "n_steps": 9,
                                                   "failed_requirements": ["assert the playlist exists"],
                                                   "collateral_damage": True})
        s_ok, s_bad = self.ad.score(self.task, ok), self.ad.score(self.task, bad)
        self.assertEqual((s_ok.reward, s_bad.reward), (1.0, 0.0))
        self.assertIn("assert the playlist exists", s_bad.feedback)
        self.assertIn("Collateral damage", s_bad.feedback)
        self.assertEqual(s_bad.to_dict(), self.ad.score(self.task, bad).to_dict())  # deterministic

    def test_lint_reject_and_infra_error(self):
        lr = self.ad.score(self.task, self.Rollout(task_id="t", metadata={"lint_reject": ["bad helper"]}))
        self.assertEqual(lr.reward, 0.0)
        self.assertIn("LINT_REJECT", lr.feedback)
        err = self.ad.score(self.task, self.Rollout(task_id="t", error="infrastructure: timeout"))
        self.assertTrue(err.raw.get("errored"))


class TestRunTrials(unittest.TestCase):
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


class TestEpisodeWorker(unittest.TestCase):
    """What _episode hands the worker subprocess, and what comes back from a crashed one."""

    PARENT = {"PATH": "/usr/bin", "HOME": "/h", "LC_ALL": "C", "APPWORLD_CACHE": "/c", "AW_MODEL_NAME": "m",
              KEY: "agent-key", "ANTHROPIC_API_KEY": "optimizer-key", "AWS_SECRET_ACCESS_KEY": "cloud",
              "GITHUB_TOKEN": "gh", "AW_SECRETS_FILE": "/repo/.env", "CAPEVOLVE_SKILLS_DIR": "/s"}

    def test_adapter_passes_the_allowlisted_env_to_the_worker(self):
        seen: dict = {}

        def fake_run(cmd, env, **kw):
            seen.update(env)
            Path(cmd[-1]).write_text(json.dumps({"infra_error": "stub"}))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        with patch.dict(os.environ, self.PARENT), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run), \
             patch.dict(os.environ, {"AW_INFRA_RETRIES": "0"}):
            adapter_mod.Adapter()._episode(Task(id="t", input={}), EX / "seed_capability", 0, work, work)
        self.assertNotIn("ANTHROPIC_API_KEY", seen)
        self.assertNotIn(KEY, seen)
        self.assertEqual(seen["APPWORLD_ROOT"], str(work))

    def test_crashed_worker_stderr_does_not_reach_feedback(self):
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
