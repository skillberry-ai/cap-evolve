# scripts/v4_t2_e1/tests/test_adapter.py
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common" / "adapters"))

import adapter as adapter_mod  # noqa: E402


REAL_TASKS_DIR = Path("/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/tasks")
KNOWN_TASK_ID = "icinga-011-aap2-job-status-alert"  # one of the 21; real dir on disk


class TestAdapterTaskResolution(unittest.TestCase):
    def test_raises_clearly_when_task_id_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                adapter_mod.Adapter()
            self.assertIn("TASK_ID", str(ctx.exception))

    def test_raises_clearly_when_task_dir_missing(self):
        with patch.dict(os.environ, {"TASK_ID": "not-a-real-task-xyz"}, clear=True):
            with self.assertRaises(FileNotFoundError):
                adapter_mod.Adapter()

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_tasks_returns_the_one_pinned_task(self):
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            tasks = a.tasks("val")
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].id, KNOWN_TASK_ID)
            task_dir = Path(tasks[0].metadata["task_dir"])
            self.assertTrue(task_dir.exists())
            self.assertEqual(task_dir.name, f"bench-v4-{KNOWN_TASK_ID}")
            # split argument is ignored on purpose — train == val == test == this task
            self.assertEqual(a.tasks("train"), tasks)
            self.assertEqual(a.tasks("test"), tasks)


class TestAdapterApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.live_prompts_dir = Path(self.tmp.name) / "live_prompts"
        self.live_prompts_dir.mkdir()
        for name in adapter_mod.PROMPT_FILES:
            (self.live_prompts_dir / name).write_text(f"seed {name}\n")
        self.env_patch = patch.dict(
            os.environ,
            {"TASK_ID": KNOWN_TASK_ID, "PARSEC_LIVE_PROMPTS_DIR": str(self.live_prompts_dir)},
            clear=True,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_apply_copies_candidate_files_into_live_prompts_dir(self):
        a = adapter_mod.Adapter()
        with tempfile.TemporaryDirectory() as cand_dir_s:
            cand_dir = Path(cand_dir_s)
            (cand_dir / "orchestrator.md").write_text("MUTATED orchestrator\n")
            a.apply(cand_dir)
            self.assertEqual(
                (self.live_prompts_dir / "orchestrator.md").read_text(),
                "MUTATED orchestrator\n",
            )
            # a file the candidate didn't touch is left alone
            self.assertEqual(
                (self.live_prompts_dir / "shared_context.md").read_text(),
                "seed shared_context.md\n",
            )


class TestAdapterScore(unittest.TestCase):
    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_score_is_zero_on_rollout_error(self):
        from cap_evolve import Rollout
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            rollout = Rollout(task_id=task.id, error="timeout after 1200s")
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.0)
            self.assertIn("timeout", score.feedback)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_score_reads_reward_from_trial_result(self):
        from cap_evolve import Rollout
        from capevolve_harbor.results import TrialResult
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            tr = TrialResult(task_id=task.id, reward=0.83)
            rollout = Rollout(task_id=task.id, metadata={"trial_result": tr.__dict__})
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.83)


class TestAdapterRunTargetJobDirResolution(unittest.TestCase):
    """Regression test for the job-dir nesting bug found by Task 6's live
    E2E smoke test: `harbor run -o <trial_dir>` writes its actual result
    one level deeper, into a timestamp-named subdirectory it creates
    itself — run_target() must resolve into that subdirectory (the same
    way capevolve_harbor.run.harbor_run() does) before calling
    parse_job_dir(), not hand it trial_dir directly.
    """

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_run_target_descends_into_harbors_timestamp_subdir(self):
        created_trial_dirs: list[Path] = []

        def fake_harbor_run(cmd, **kwargs):
            # cmd == ["harbor", "run", "--config", <cfg_path>, "--n-concurrent", "1"]
            cfg_path = Path(cmd[3])
            trial_dir = cfg_path.parent
            created_trial_dirs.append(trial_dir)

            # Mimic real harbor: trial_dir holds harbor_config.json (already
            # written by run_target) plus a timestamp-named subdir that
            # harbor itself creates, containing the real per-trial result.
            job_dir = trial_dir / "2026-09-18__09-17-39"
            trial_sub = job_dir / "bench-v4-icinga-011-aap2-job-sta__qtXiDNr"
            verifier_dir = trial_sub / "verifier"
            verifier_dir.mkdir(parents=True)
            (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.58}))
            (trial_sub / "config.json").write_text(
                json.dumps({"task": {"name": KNOWN_TASK_ID}})
            )
            return subprocess.CompletedProcess(cmd, 0)

        try:
            with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
                a = adapter_mod.Adapter()
                task = a.tasks("val")[0]
                with patch.object(
                    adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_harbor_run):
                    rollout = a.run_target(task, ctx=None)

            self.assertIsNone(rollout.error)
            score = a.score(task, rollout)
            self.assertAlmostEqual(score.reward, 0.58)
        finally:
            for d in created_trial_dirs:
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
