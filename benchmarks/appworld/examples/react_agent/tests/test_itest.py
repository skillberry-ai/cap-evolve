"""scripts/itest.sh, scripts/assert_itest.py and capevolve.itest.yaml: the one-task regression test.

Modelled on benchmarks/tau2/examples/airline/{itest.sh, assert_itest.py, capevolve.itest.yaml}. The asserter
is run against synthetic run dirs laid out like cap-evolve's (baseline.json, final.json,
report.md, state.json, rollouts/<split>/*.json).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The modules under test live in ../scripts. `cap_evolve` normally comes from the installed
# package; core/ is a fallback so that
#     python3 benchmarks/appworld/examples/react_agent/tests/test_itest.py -v
# works from a clean shell, as in benchmarks/parsec/examples/rca_prompts/tests.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.append(str(Path(__file__).resolve().parents[5] / "core"))

import assert_itest  # noqa: E402

TAU2 = EX.parent / "tau2_airline"
ITEST_TASK = "82e2fac_1"


def _spec(path: Path) -> dict:
    """The flat `key: value` pairs of a cap-evolve spec (comments dropped)."""
    out = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].rstrip()
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class TestAssertItest(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp()) / "run_itest"
        self.addCleanup(shutil.rmtree, self.run.parent, ignore_errors=True)
        (self.run / "rollouts" / "val").mkdir(parents=True)
        (self.run / "rollouts" / "test").mkdir(parents=True)

    def _finish(self, base_val=0.0, final_test=0.0, iterations=1):
        (self.run / "baseline.json").write_text(json.dumps({"val": {"reward": base_val}}))
        (self.run / "final.json").write_text(json.dumps({"test": {"reward": final_test}}))
        (self.run / "report.md").write_text("# report\n")
        (self.run / "state.json").write_text(json.dumps({"spent": {"iterations": iterations}}))

    def _rollout(self, split="val", cand="seed", error=None, meta=None, feedback="FAILED: 1/2 requirement checks passed."):
        rec = {"input": {"instruction": "x"},
               "rollout": {"task_id": ITEST_TASK, "error": error, "metadata": meta or {"success": False}},
               "score": {"task_id": ITEST_TASK, "reward": 0.0, "feedback": feedback}}
        (self.run / "rollouts" / split / f"{ITEST_TASK}__{cand}__t0.json").write_text(json.dumps(rec))

    def test_completed_non_regressing_run_passes(self):
        self._finish(0.0, 0.0)
        self._rollout("val", "seed")
        self._rollout("test", "seed")
        v = assert_itest.check(self.run)
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["checks"]["rollouts"], 2)

    def test_regression_fails(self):
        self._finish(1.0, 0.0)
        self._rollout()
        self.assertFalse(assert_itest.check(self.run)["checks"]["no_regression"])

    def test_no_iteration_fails(self):
        self._finish(0.0, 0.0, iterations=0)
        self._rollout()
        self.assertFalse(assert_itest.check(self.run)["ok"])

    def test_unfinished_run_fails(self):
        self._rollout()
        v = assert_itest.check(self.run)
        self.assertFalse(v["ok"])
        self.assertFalse(v["checks"]["completed"])

    def test_infra_error_is_not_a_pass(self):
        # A broken key or model scores 0.0 like a failed task; it must fail the itest, not pass it.
        self._finish(0.0, 0.0)
        self._rollout(error="infrastructure: worker exited 1 without output (AuthenticationError)")
        v = assert_itest.check(self.run)
        self.assertFalse(v["ok"])
        self.assertIn("AuthenticationError", v["checks"]["episode_failures"][0]["error"])

    def test_lint_reject_is_not_a_pass(self):
        self._finish(0.0, 0.0)
        self._rollout(meta={"lint_reject": ["policy/instructions.txt: missing"]})
        self.assertFalse(assert_itest.check(self.run)["checks"]["episodes_ran"])

    def test_no_rollouts_fails(self):
        self._finish(0.0, 0.0)
        self.assertFalse(assert_itest.check(self.run)["checks"]["episodes_ran"])

    def test_gold_marker_in_a_record_fails(self):
        self._finish(0.0, 0.0)
        self._rollout(feedback='FAILED ... {"trace": "expected GOLD"}')
        v = assert_itest.check(self.run)
        self.assertFalse(v["ok"])
        self.assertTrue(v["checks"]["gold_markers_in_rollouts"])

    def test_trace_in_the_metadata_fails(self):
        self._finish(0.0, 0.0)
        self._rollout(meta={"success": False, "failures": [{"requirement": "r", "trace": "gold"}]})
        self.assertFalse(assert_itest.check(self.run)["checks"]["gold_free"])

    def test_gold_file_name_anywhere_fails(self):
        self._finish(0.0, 0.0)
        self._rollout(feedback="read /data/tasks/x/ground_truth/answer.json")
        self.assertFalse(assert_itest.check(self.run)["checks"]["gold_free"])

    def test_the_agents_own_step_trace_is_not_gold(self):
        # cap-evolve's Rollout.trace holds the agent's steps; it is not AppWorld's failure trace.
        self._finish(0.0, 0.0)
        rec = {"input": {}, "rollout": {"task_id": ITEST_TASK, "error": None, "metadata": {"success": False},
                                        "trace": [{"step": 1, "code": "apis.supervisor.complete_task()"}]},
               "score": {"task_id": ITEST_TASK, "reward": 0.0, "feedback": "FAILED"}}
        (self.run / "rollouts" / "val" / f"{ITEST_TASK}__seed__t0.json").write_text(json.dumps(rec))
        self.assertTrue(assert_itest.check(self.run)["checks"]["gold_free"])

    def test_cli_exit_code(self):
        self._finish(0.0, 0.0)
        self._rollout()
        r = subprocess.run([sys.executable, str(EX / "scripts" / "assert_itest.py"), str(self.run)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])
        r = subprocess.run([sys.executable, str(EX / "scripts" / "assert_itest.py"), str(self.run / "nope")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


class TestItestSpec(unittest.TestCase):
    def test_split_is_one_search_task(self):
        split = json.loads((EX / "itest_split.json").read_text())
        self.assertEqual(split, {"train": [ITEST_TASK], "val": [ITEST_TASK], "test": [ITEST_TASK]})

    def test_same_budget_shape_as_tau2_itest(self):
        ours, tau2 = _spec(EX / "capevolve.itest.yaml"), _spec(TAU2 / "capevolve.itest.yaml")
        for k in ("max_iterations", "num_trials", "stall", "max_metric_calls", "gate_mode", "gate_k_se",
                  "algorithm_skill", "algorithm_focus", "optimizer_skill", "max_usd", "max_optimizer_usd"):
            self.assertEqual(ours[k], tau2[k], k)

    def test_same_search_setup_as_the_full_spec(self):
        ours, full = _spec(EX / "capevolve.itest.yaml"), _spec(EX / "capevolve.yaml")
        for k in ("capabilities", "capability_path", "actions", "capability_sources", "runner_repo_path",
                  "optimizer_skill", "optimizer_model", "optimizer_instructions_file", "target_model",
                  "algorithm_skill", "algorithm_focus", "orchestration_mode", "memory_skill",
                  "dataset_source", "gate_mode", "gate_k_se", "protected_paths", "store"):
            self.assertEqual(ours[k], full[k], k)
        self.assertEqual(ours["split_ids_file"], "itest_split.json")

    def test_itest_runs_through_the_real_launch_path(self):
        sh = (EX / "scripts" / "itest.sh").read_text()
        self.assertIn("setup_project.sh", sh)
        self.assertIn("AW_SPEC=capevolve.itest.yaml bash \"$EX/scripts/launch_cape_hc.sh\"", sh)
        self.assertIn("assert_itest.py", sh)
        self.assertIn('--spec "$P/${AW_SPEC:-capevolve.yaml}"', (EX / "scripts" / "launch_cape_hc.sh").read_text())


if __name__ == "__main__":
    unittest.main()
