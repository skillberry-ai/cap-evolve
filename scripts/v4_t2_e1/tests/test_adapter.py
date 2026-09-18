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
# adapter.py adds the repo root to sys.path itself (so `capevolve_harbor` imports),
# but `cap_evolve` lives under core/ — which only an installed cap-evolve or an
# explicit PYTHONPATH=core provides. Add it here, in the TEST, rather than in
# adapter.py: a second copy of cap_evolve ahead of the installed one inside a
# real `cap-evolve run` process would be a far worse bug than an awkward test
# invocation. This is what makes
#     python3 scripts/v4_t2_e1/tests/test_adapter.py -v
# work from a clean shell with no PYTHONPATH set.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core"))

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
        # Guard rail for the C2 corruption class: assert BEFORE any mutation
        # that this Adapter's live-prompts target is inside this test's own
        # tmpdir, so no future refactor (e.g. reintroducing a module-level
        # constant computed at import time) can let this test write into the
        # real shared parsec-live clone.
        self.assertEqual(a.live_prompts_dir, self.live_prompts_dir)
        self.assertTrue(
            str(a.live_prompts_dir).startswith(self.tmp.name),
            f"test would write outside its own tmpdir: {a.live_prompts_dir}",
        )
        with tempfile.TemporaryDirectory() as cand_dir_s:
            cand_dir = Path(cand_dir_s)
            # Must clear MIN_ORCHESTRATOR_BYTES — a 21-byte orchestrator.md is
            # exactly the corrupted-fixture shape apply() now refuses.
            mutated = "MUTATED orchestrator\n" + ("filler line to reach a plausible size\n" * 40)
            (cand_dir / "orchestrator.md").write_text(mutated)
            a.apply(cand_dir)
            self.assertEqual(
                (self.live_prompts_dir / "orchestrator.md").read_text(),
                mutated,
            )
            # a file the candidate didn't touch is left alone
            self.assertEqual(
                (self.live_prompts_dir / "shared_context.md").read_text(),
                "seed shared_context.md\n",
            )

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_apply_refuses_an_implausibly_short_orchestrator(self):
        """The C2 corruption chain: a test fixture's 21-byte "MUTATED
        orchestrator\\n" reached the live parsec-live clone and was then frozen
        into 21 seed snapshots. The real prompt is ~11.7KB, so a candidate
        whose orchestrator.md is a few dozen bytes is truncated or placeholder
        content and must be refused rather than served.
        """
        a = adapter_mod.Adapter()
        before = {
            name: (self.live_prompts_dir / name).read_text()
            for name in adapter_mod.PROMPT_FILES
        }
        with tempfile.TemporaryDirectory() as cand_dir_s:
            cand_dir = Path(cand_dir_s)
            (cand_dir / "orchestrator.md").write_text("MUTATED orchestrator\n")
            # A sibling file that WOULD otherwise be copied, to prove the refusal
            # happens before any write, not partway through the loop.
            (cand_dir / "shared_context.md").write_text("x" * 2000)
            with self.assertRaises(ValueError) as ctx:
                a.apply(cand_dir)
        self.assertIn("orchestrator.md", str(ctx.exception))
        for name, original in before.items():
            self.assertEqual(
                (self.live_prompts_dir / name).read_text(), original,
                f"{name} must be left completely unmodified by a refused apply()",
            )


class TestAdapterLiveTeardown(unittest.TestCase):
    """apply() mutates a SHARED, long-lived resource — the one parsec-live
    clone every task's trials talk to. The base CapabilityAdapter.live() has an
    empty finally, so a crash anywhere between apply() and the end of an
    evaluation left that candidate's prompts serving indefinitely: the next
    run's "baseline" would silently be the previous run's mutant. live() must
    snapshot the 8 PROMPT_FILES on entry and restore them in a finally.

    harness.py's _live() enters this context manager around the WHOLE
    evaluation (see its call site at harness.py's redirect_stdout block), so
    per-evaluation scoping is the right granularity.
    """

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
        self.candidate = Path(self.tmp.name) / "candidate"
        self.candidate.mkdir()
        self.mutated = "CANDIDATE orchestrator\n" + ("body line\n" * 80)
        (self.candidate / "orchestrator.md").write_text(self.mutated)
        (self.candidate / "cost_agent.md").write_text("CANDIDATE cost agent\n")

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    def _current(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for name in adapter_mod.PROMPT_FILES:
            p = self.live_prompts_dir / name
            out[name] = p.read_text() if p.exists() else None
        return out

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_live_applies_the_candidate_inside_the_context(self):
        a = adapter_mod.Adapter()
        with a.live(self.candidate) as ctx:
            self.assertEqual((self.live_prompts_dir / "orchestrator.md").read_text(),
                             self.mutated)
            self.assertEqual((self.live_prompts_dir / "cost_agent.md").read_text(),
                             "CANDIDATE cost agent\n")
        # ctx contract: the base class yields candidate_dir, callers pass it to
        # run_target as `ctx` — the override must not change that.
        self.assertEqual(Path(str(ctx)), self.candidate)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_live_restores_the_snapshot_after_a_crash_inside_the_block(self):
        a = adapter_mod.Adapter()
        before = self._current()
        with self.assertRaises(RuntimeError):
            with a.live(self.candidate):
                self.assertEqual((self.live_prompts_dir / "orchestrator.md").read_text(),
                                 self.mutated)
                raise RuntimeError("VPN dropped mid-trial")
        self.assertEqual(self._current(), before)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_live_restores_the_snapshot_on_a_clean_exit_too(self):
        a = adapter_mod.Adapter()
        before = self._current()
        with a.live(self.candidate):
            pass
        self.assertEqual(self._current(), before)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_live_removes_a_file_that_did_not_exist_before_entry(self):
        """Restore means restore: a prompt the candidate ADDS must be deleted on
        exit, not left behind as a permanent addition to the live clone."""
        (self.live_prompts_dir / "cost_agent.md").unlink()
        a = adapter_mod.Adapter()
        with a.live(self.candidate):
            self.assertTrue((self.live_prompts_dir / "cost_agent.md").exists())
        self.assertFalse((self.live_prompts_dir / "cost_agent.md").exists())

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_live_restores_even_when_apply_itself_refuses(self):
        """A candidate rejected by the MIN_ORCHESTRATOR_BYTES floor must not
        leave the live clone in a half-state either."""
        bad = Path(self.tmp.name) / "bad_candidate"
        bad.mkdir()
        (bad / "orchestrator.md").write_text("MUTATED orchestrator\n")
        a = adapter_mod.Adapter()
        before = self._current()
        with self.assertRaises(ValueError):
            with a.live(bad):
                pass  # pragma: no cover — apply() raises before the yield
        self.assertEqual(self._current(), before)


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


class TestAdapterInfraErrorPropagation(unittest.TestCase):
    """parse_job_dir() sets TrialResult.error only when a trial produced NO
    score at all — an image build failure, an agent-setup timeout, an agent
    timeout. That is missing data, not a reward of 0.0, and only Rollout.error
    tells the harness to exclude it from the mean instead of feeding the
    optimizer a phantom capability regression. run_target() computed
    trial_result.error and then dropped it on the floor.
    """

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_run_target_surfaces_an_unscored_trial_as_rollout_error(self):
        created_trial_dirs: list[Path] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] != "harbor":
                return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")
            trial_dir = Path(cmd[3]).parent
            created_trial_dirs.append(trial_dir)
            # No verifier/reward.* at all: harbor blew up before scoring.
            trial_sub = trial_dir / "2026-09-18__09-17-39" / "bench-v4-icinga-011__zz"
            trial_sub.mkdir(parents=True)
            (trial_sub / "config.json").write_text(json.dumps({"task": {"name": KNOWN_TASK_ID}}))
            (trial_sub / "result.json").write_text(json.dumps({
                "exception_info": {
                    "exception_type": "ImageBuildError",
                    "exception_message": "some infra failure",
                }
            }))
            return subprocess.CompletedProcess(cmd, 0)

        try:
            with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
                a = adapter_mod.Adapter()
                task = a.tasks("val")[0]
                with patch.object(
                    adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                    rollout = a.run_target(task, ctx=None)

            self.assertIsNotNone(
                rollout.error,
                "an unscored trial must set Rollout.error, not look like reward 0.0",
            )
            self.assertIn("some infra failure", rollout.error)
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.0)
            self.assertIn(
                "some infra failure", score.feedback,
                "the optimizer must see the infra cause, not a generic zero-reward",
            )
        finally:
            for d in created_trial_dirs:
                shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_run_target_carries_cost_and_tokens_onto_the_rollout(self):
        created_trial_dirs: list[Path] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] != "harbor":
                return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")
            trial_dir = Path(cmd[3]).parent
            created_trial_dirs.append(trial_dir)
            trial_sub = trial_dir / "2026-09-18__09-17-39" / "bench-v4-icinga-011__zz"
            (trial_sub / "verifier").mkdir(parents=True)
            (trial_sub / "verifier" / "reward.json").write_text(json.dumps({"reward": 1.0}))
            (trial_sub / "config.json").write_text(json.dumps({"task": {"name": KNOWN_TASK_ID}}))
            (trial_sub / "result.json").write_text(
                json.dumps({"cost_usd": 1.37, "tokens": 42000})
            )
            return subprocess.CompletedProcess(cmd, 0)

        try:
            with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
                a = adapter_mod.Adapter()
                task = a.tasks("val")[0]
                with patch.object(
                    adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                    rollout = a.run_target(task, ctx=None)
            self.assertIsNone(rollout.error)
            self.assertEqual(rollout.cost_usd, 1.37)
            self.assertEqual(rollout.tokens, 42000)
            tr = rollout.metadata["trial_result"]
            self.assertEqual(rollout.cost_usd, tr["cost_usd"])
            self.assertEqual(rollout.tokens, tr["tokens"])
        finally:
            for d in created_trial_dirs:
                shutil.rmtree(d, ignore_errors=True)


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
            # run_target() also shells out to install_seeds.py before harbor
            # (see TestAdapterRunTargetSeedsSimulationData) — let that succeed
            # silently; this test is only about harbor's own output layout.
            if cmd[0] != "harbor":
                return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")
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


class TestAdapterRunTargetSeedsSimulationData(unittest.TestCase):
    """The 5 MCP harness services are SHARED across all 21 tasks, and each one
    keeps serving whatever dataset was PUT into it last. install_seeds.py's own
    docstring spells out the consequence: "A service that is reachable but
    unseeded serves whatever the previous task left behind, which produces a
    plausible reward for the wrong dataset." So run_target() must install this
    task's seeds immediately before every trial — exactly as the reference
    driver (v4_2026-09-16/run_full34.py's run_seed()) does — not once per
    stack bring-up.
    """

    def _fake_harbor_output(self, trial_dir: Path, reward: float) -> None:
        job_dir = trial_dir / "2026-09-18__09-17-39"
        trial_sub = job_dir / "bench-v4-icinga-011-aap2-job-sta__qtXiDNr"
        verifier_dir = trial_sub / "verifier"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "reward.json").write_text(json.dumps({"reward": reward}))
        (trial_sub / "config.json").write_text(json.dumps({"task": {"name": KNOWN_TASK_ID}}))

    @staticmethod
    def _index_of(calls: list[list[str]], needle: str) -> int:
        for i, cmd in enumerate(calls):
            if any(needle in str(part) for part in cmd):
                return i
        raise AssertionError(f"no subprocess.run call contained {needle!r}; saw {calls}")

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_run_target_installs_seeds_before_harbor_run(self):
        calls: list[list[str]] = []
        created_trial_dirs: list[Path] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[0] == "harbor":
                trial_dir = Path(cmd[3]).parent
                created_trial_dirs.append(trial_dir)
                self._fake_harbor_output(trial_dir, 0.42)
                return subprocess.CompletedProcess(cmd, 0)
            return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")

        try:
            with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
                a = adapter_mod.Adapter()
                task = a.tasks("val")[0]
                with patch.object(
                    adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                    rollout = a.run_target(task, ctx=None)

            self.assertIsNone(rollout.error)
            seed_idx = self._index_of(calls, "install_seeds.py")
            harbor_idx = self._index_of(calls, "harbor")
            self.assertLess(
                seed_idx, harbor_idx,
                "install_seeds.py must run BEFORE harbor run, not after",
            )
            self.assertIn(
                task.metadata["task_dir"], [str(p) for p in calls[seed_idx]],
                "install_seeds.py must be given this task's own task dir",
            )
        finally:
            for d in created_trial_dirs:
                shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(REAL_TASKS_DIR.exists(), "real bench-v4 tasks dir not present")
    def test_seeding_failure_is_an_infra_error_not_a_zero_reward(self):
        """A failed seed must surface as Rollout.error (infra noise) so the
        harness excludes the trial, and must NOT proceed to run harbor against
        the previous task's dataset."""
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if any("install_seeds.py" in str(part) for part in cmd):
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="port 8088 refused")
            raise AssertionError(f"should not have reached {cmd!r} after a seed failure")

        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            with patch.object(
                adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
            ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                rollout = a.run_target(task, ctx=None)

        self.assertIsNotNone(rollout.error)
        self.assertIn("install_seeds", rollout.error)
        self.assertIn("port 8088 refused", rollout.error)
        self.assertEqual(len(calls), 1, f"harbor must not have been invoked; saw {calls}")


if __name__ == "__main__":
    unittest.main()
