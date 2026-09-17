# scripts/v4_t2_e1/tests/test_scaffold_projects.py
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
