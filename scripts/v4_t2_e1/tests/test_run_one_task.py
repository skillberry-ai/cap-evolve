# scripts/v4_t2_e1/tests/test_run_one_task.py
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_one_task  # noqa: E402


class TestResolveNextTaskId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.capevolve_dir = Path(self.tmp.name) / ".capevolve"
        self.capevolve_dir.mkdir()
        self.task_ids = ["task-a", "task-b", "task-c"]

    def tearDown(self):
        self.tmp.cleanup()

    def _mark_done(self, task_id: str, run_ts: str = "20260101_000000") -> None:
        run_dir = self.capevolve_dir / f"v4_t2_e1_{task_id}" / f"run_{run_ts}"
        run_dir.mkdir(parents=True)
        (run_dir / "final.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    def test_returns_first_task_when_none_done(self):
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-a",
        )

    def test_skips_tasks_with_a_final_json(self):
        self._mark_done("task-a")
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-b",
        )

    def test_returns_none_when_all_done(self):
        for t in self.task_ids:
            self._mark_done(t)
        self.assertIsNone(run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids))

    def test_a_run_dir_without_final_json_does_not_count_as_done(self):
        stuck = self.capevolve_dir / "v4_t2_e1_task-a" / "run_20260101_000000"
        stuck.mkdir(parents=True)  # crashed mid-run: no final.json written
        self.assertEqual(
            run_one_task.resolve_next_task_id(self.capevolve_dir, self.task_ids),
            "task-a",
        )


class TestRunTask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        self.capevolve_dir = self.repo_root / ".capevolve"
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        proj.mkdir(parents=True)
        # A valid, resolvable project needs real (non-dangling) adapters/optimizer
        # symlinks, per the Task 5 pre-flight check.
        common = self.capevolve_dir / "v4_t2_e1_common"
        (common / "adapters").mkdir(parents=True)
        (common / "optimizer").mkdir(parents=True)
        (proj / "adapters").symlink_to(common / "adapters", target_is_directory=True)
        (proj / "optimizer").symlink_to(common / "optimizer", target_is_directory=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_invokes_cap_evolve_with_expected_project_and_task_id_env(self):
        captured = {}

        def fake_run(cmd, env=None, cwd=None):
            captured["cmd"] = cmd
            captured["env"] = env
            captured["cwd"] = cwd

            class _Result:
                returncode = 0

            return _Result()

        with patch("subprocess.run", side_effect=fake_run):
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 0)
        self.assertIn("cap-evolve", captured["cmd"])
        self.assertIn("run", captured["cmd"])
        self.assertIn(str(self.capevolve_dir / "v4_t2_e1_task-a" / "project"), captured["cmd"])
        self.assertEqual(captured["env"]["TASK_ID"], "task-a")
        self.assertEqual(captured["cwd"], str(self.repo_root))

    def test_propagates_nonzero_exit_code(self):
        def fake_run(cmd, env=None, cwd=None):
            class _Result:
                returncode = 17

            return _Result()

        with patch("subprocess.run", side_effect=fake_run):
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 17)


class TestRunTaskSymlinkPreflight(unittest.TestCase):
    """Task 2's `_ensure_symlink()` uses `Path.symlink_to()`, which does not
    validate its target exists, so a scaffold run against a not-yet-existing
    common/ source can silently leave a dangling `adapters` or `optimizer`
    symlink under a task's project/. run_task() must catch that itself,
    before ever invoking `cap-evolve run`.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        self.capevolve_dir = self.repo_root / ".capevolve"
        self.proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        self.proj.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_adapters_symlink_aborts_before_subprocess(self):
        # adapters is missing entirely; optimizer resolves fine.
        real_optimizer = self.capevolve_dir / "v4_t2_e1_common" / "optimizer"
        real_optimizer.mkdir(parents=True)
        (self.proj / "optimizer").symlink_to(real_optimizer, target_is_directory=True)

        with patch("subprocess.run") as mock_run:
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 3)
        mock_run.assert_not_called()

    def test_dangling_adapters_symlink_aborts_before_subprocess(self):
        # adapters points at a target that does not exist (dangling); optimizer resolves fine.
        (self.proj / "adapters").symlink_to(
            self.capevolve_dir / "v4_t2_e1_common" / "adapters", target_is_directory=True
        )
        real_optimizer = self.capevolve_dir / "v4_t2_e1_common" / "optimizer"
        real_optimizer.mkdir(parents=True)
        (self.proj / "optimizer").symlink_to(real_optimizer, target_is_directory=True)

        with patch("subprocess.run") as mock_run:
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 3)
        mock_run.assert_not_called()

    def test_dangling_optimizer_symlink_aborts_before_subprocess(self):
        # adapters resolves fine; optimizer is dangling.
        real_adapters = self.capevolve_dir / "v4_t2_e1_common" / "adapters"
        real_adapters.mkdir(parents=True)
        (self.proj / "adapters").symlink_to(real_adapters, target_is_directory=True)
        (self.proj / "optimizer").symlink_to(
            self.capevolve_dir / "v4_t2_e1_common" / "optimizer", target_is_directory=True
        )

        with patch("subprocess.run") as mock_run:
            code = run_one_task.run_task(
                "task-a", capevolve_dir=self.capevolve_dir, repo_root=self.repo_root
            )
        self.assertEqual(code, 3)
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
