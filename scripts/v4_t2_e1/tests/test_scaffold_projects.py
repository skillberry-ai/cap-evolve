# scripts/v4_t2_e1/tests/test_scaffold_projects.py
from __future__ import annotations

import importlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scaffold_projects  # noqa: E402


class TestScaffoldProjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.capevolve_dir = Path(self.tmp.name) / ".capevolve"
        # A fake prompts_dir standing in for _run/parsec-live/config/prompts/ —
        # real 8-file fixture, not the actual live prompts (keeps the test
        # hermetic and fast).
        self.prompts_dir = Path(self.tmp.name) / "fake_prompts"
        self.prompts_dir.mkdir(parents=True)
        for name in scaffold_projects.PROMPT_FILES:
            (self.prompts_dir / name).write_text(f"# seed content for {name}\n")
        # Fake common/ source, standing in for scripts/v4_t2_e1/common/.
        self.common_adapters_src = Path(self.tmp.name) / "common_src" / "adapters"
        self.common_optimizer_src = Path(self.tmp.name) / "common_src" / "optimizer"
        self.common_adapters_src.mkdir(parents=True)
        self.common_optimizer_src.mkdir(parents=True)
        (self.common_adapters_src / "adapter.py").write_text("# fake adapter\n")
        (self.common_optimizer_src / "INSTRUCTIONS.md").write_text("# fake instructions\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_one_project_per_task_with_all_seed_files(self):
        task_ids = ["task-a", "task-b"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        for tid in task_ids:
            proj = self.capevolve_dir / f"v4_t2_e1_{tid}" / "project"
            for name in scaffold_projects.PROMPT_FILES:
                self.assertTrue((proj / "seed_capability" / name).exists(),
                                 f"missing {name} for {tid}")
            self.assertTrue((proj / "capevolve.yaml").exists())
            self.assertTrue((proj / "split_ids.json").exists())

    def test_project_adapters_symlink_resolves_to_common_source(self):
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        resolved = (proj / "adapters").resolve()
        self.assertEqual(resolved, self.common_adapters_src.resolve())
        self.assertTrue((proj / "adapters" / "adapter.py").exists())

    def test_run_dir_parent_is_unique_per_task(self):
        # The whole point of the nested layout: two tasks' projects must not
        # share a parent directory (that parent is where cap-evolve run puts
        # run_*/ — see deviation 1 in the plan header).
        task_ids = ["task-a", "task-b"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj_a = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        proj_b = self.capevolve_dir / "v4_t2_e1_task-b" / "project"
        self.assertNotEqual(proj_a.resolve().parent, proj_b.resolve().parent)

    def test_split_ids_json_pins_train_val_test_to_the_one_task(self):
        import json
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        data = json.loads((proj / "split_ids.json").read_text())
        self.assertEqual(data, {"train": ["task-a"], "val": ["task-a"], "test": ["task-a"]})

    def test_capevolve_yaml_has_required_keys(self):
        task_ids = ["task-a"]
        scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        proj = self.capevolve_dir / "v4_t2_e1_task-a" / "project"
        text = (proj / "capevolve.yaml").read_text()
        for key in ("optimizer_skill", "optimizer_model", "algorithm_skill",
                    "target_model", "capabilities", "num_trials", "max_iterations",
                    "stall", "max_usd", "max_optimizer_usd", "stop_at_reward",
                    "split_ids_file"):
            self.assertIn(key, text, f"missing key {key!r} in capevolve.yaml")

    def test_scaffold_is_idempotent(self):
        task_ids = ["task-a"]
        first = scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        second = scaffold_projects.scaffold_all(
            self.capevolve_dir, prompts_dir=self.prompts_dir, task_ids=task_ids,
            common_adapters_src=self.common_adapters_src,
            common_optimizer_src=self.common_optimizer_src,
        )
        self.assertEqual(sorted(first), sorted(second))


class TestParsecV4NIsEnvOverridable(unittest.TestCase):
    """adapter.py resolves V4N from the PARSEC_V4N env var; the scaffolder
    hardcoded the same path. Two sources of truth for "which parsec checkout"
    means a scaffolded seed snapshot can be frozen from one tree while trials
    run against another — the exact shape of the v4_old base-commit divergence.
    """

    def test_module_reads_the_same_env_var_adapter_py_does(self):
        override = Path(tempfile.gettempdir()) / "fake-parsec-v4n"
        with patch.dict(os.environ, {"PARSEC_V4N": str(override)}, clear=False):
            reloaded = importlib.reload(scaffold_projects)
            try:
                self.assertEqual(reloaded.PARSEC_V4N, override)
                self.assertEqual(
                    reloaded.PROMPTS_DIR,
                    override / "_run" / "parsec-live" / "config" / "prompts",
                )
            finally:
                importlib.reload(scaffold_projects)

    def test_default_matches_adapter_pys_default(self):
        with patch.dict(os.environ, {}, clear=True):
            reloaded = importlib.reload(scaffold_projects)
            try:
                self.assertEqual(
                    reloaded.PARSEC_V4N,
                    Path("/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16"),
                )
            finally:
                importlib.reload(scaffold_projects)


class TestMainChecksItsSources(unittest.TestCase):
    """_ensure_symlink() uses Path.symlink_to(), which does not validate its
    target exists — so main() scaffolding against a missing common/ source
    produced 21 projects' worth of dangling symlinks and exited 0. Task 5's
    runner catches that later, per task, but the scaffolder should refuse up
    front.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.tmp.name) / "fake_prompts"
        self.prompts_dir.mkdir(parents=True)
        for name in scaffold_projects.PROMPT_FILES:
            (self.prompts_dir / name).write_text(f"# seed content for {name}\n")
        self.present = Path(self.tmp.name) / "present"
        self.present.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run_main(self, *, adapters: Path, optimizer: Path):
        missing_capevolve = Path(self.tmp.name) / ".capevolve"
        with patch.object(sys, "argv", ["scaffold_projects.py", "--only", "task-a"]), \
             patch.object(scaffold_projects, "TASK_IDS", ["task-a"]), \
             patch.object(scaffold_projects, "PROMPTS_DIR", self.prompts_dir), \
             patch.object(scaffold_projects, "CAPEVOLVE_DIR", missing_capevolve), \
             patch.object(scaffold_projects, "COMMON_ADAPTERS_SRC", adapters), \
             patch.object(scaffold_projects, "COMMON_OPTIMIZER_SRC", optimizer), \
             patch.object(scaffold_projects, "scaffold_all") as mock_scaffold, \
             patch("sys.stderr", new_callable=io.StringIO) as err:
            code = scaffold_projects.main()
        return code, mock_scaffold, err.getvalue()

    def test_missing_adapters_source_refuses_before_scaffolding(self):
        code, mock_scaffold, err = self._run_main(
            adapters=Path(self.tmp.name) / "nope_adapters", optimizer=self.present,
        )
        self.assertEqual(code, 1)
        mock_scaffold.assert_not_called()
        self.assertIn("nope_adapters", err)

    def test_missing_optimizer_source_refuses_before_scaffolding(self):
        code, mock_scaffold, err = self._run_main(
            adapters=self.present, optimizer=Path(self.tmp.name) / "nope_optimizer",
        )
        self.assertEqual(code, 1)
        mock_scaffold.assert_not_called()
        self.assertIn("nope_optimizer", err)

    def test_both_sources_present_proceeds(self):
        code, mock_scaffold, _ = self._run_main(
            adapters=self.present, optimizer=self.present,
        )
        self.assertEqual(code, 0)
        mock_scaffold.assert_called_once()
        # main() must scaffold from exactly the paths it validated, not from
        # scaffold_all()'s def-time defaults.
        kwargs = mock_scaffold.call_args.kwargs
        self.assertEqual(kwargs["prompts_dir"], self.prompts_dir)
        self.assertEqual(kwargs["common_adapters_src"], self.present)
        self.assertEqual(kwargs["common_optimizer_src"], self.present)


class TestEnsureSymlinkUsesTopLevelOs(unittest.TestCase):
    def test_module_imports_os_at_the_top_level(self):
        """_ensure_symlink() reached for `__import__("os").path.relpath(...)`
        inline. A module-level import is the same behaviour without the
        indirection — and the module now needs `os` for PARSEC_V4N anyway."""
        self.assertIs(scaffold_projects.os, os)
        source = Path(scaffold_projects.__file__).read_text()
        self.assertNotIn('__import__("os")', source)


if __name__ == "__main__":
    unittest.main()
