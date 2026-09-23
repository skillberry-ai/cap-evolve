# scripts/v4_t2_e1/tests/test_adapter.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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


# adapter_mod.TASKS_DIR is derived from $PARSEC_V4N via parsec_paths.py (may
# be None if it's unset) — using it here, rather than a second hardcoded
# literal, is the fix for the exact defect this constant used to encode:
# REAL_TASKS_DIR previously named a Mac-only path completely independent of
# $PARSEC_V4N, so these tests silently skipped on any other machine
# regardless of what PARSEC_V4N was set to.
REAL_TASKS_DIR = adapter_mod.TASKS_DIR
_REAL_TASKS_DIR_PRESENT = REAL_TASKS_DIR is not None and REAL_TASKS_DIR.exists()
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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


class TestResolveDockerHost(unittest.TestCase):
    def test_prefers_docker_host_env_var_when_set(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "unix:///run/user/1000/podman/podman.sock"}, clear=True):
            self.assertEqual(
                adapter_mod._resolve_docker_host(),
                "unix:///run/user/1000/podman/podman.sock",
            )

    def test_falls_back_to_podman_machine_inspect_when_unset(self):
        fake_stdout = json.dumps([
            {"ConnectionInfo": {"PodmanSocket": {"Path": "/tmp/podman-machine.sock"}}}
        ])
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(
                 adapter_mod.subprocess, "run",
                 return_value=subprocess.CompletedProcess([], 0, stdout=fake_stdout, stderr=""),
             ) as mock_run:
            result = adapter_mod._resolve_docker_host()
            self.assertEqual(result, "unix:///tmp/podman-machine.sock")
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args.args[0][:2], ["podman", "machine"])


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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_live_restores_the_snapshot_after_a_crash_inside_the_block(self):
        a = adapter_mod.Adapter()
        before = self._current()
        with self.assertRaises(RuntimeError):
            with a.live(self.candidate):
                self.assertEqual((self.live_prompts_dir / "orchestrator.md").read_text(),
                                 self.mutated)
                raise RuntimeError("VPN dropped mid-trial")
        self.assertEqual(self._current(), before)

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_live_restores_the_snapshot_on_a_clean_exit_too(self):
        a = adapter_mod.Adapter()
        before = self._current()
        with a.live(self.candidate):
            pass
        self.assertEqual(self._current(), before)

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_live_removes_a_file_that_did_not_exist_before_entry(self):
        """Restore means restore: a prompt the candidate ADDS must be deleted on
        exit, not left behind as a permanent addition to the live clone."""
        (self.live_prompts_dir / "cost_agent.md").unlink()
        a = adapter_mod.Adapter()
        with a.live(self.candidate):
            self.assertTrue((self.live_prompts_dir / "cost_agent.md").exists())
        self.assertFalse((self.live_prompts_dir / "cost_agent.md").exists())

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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
    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_score_is_zero_on_rollout_error(self):
        from cap_evolve import Rollout
        with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
            a = adapter_mod.Adapter()
            task = a.tasks("val")[0]
            rollout = Rollout(task_id=task.id, error="timeout after 1200s")
            score = a.score(task, rollout)
            self.assertEqual(score.reward, 0.0)
            self.assertIn("timeout", score.feedback)

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_run_target_cost_and_tokens_are_zero_when_no_usage_log_matches(self):
        """cost_usd/tokens on the Rollout come from parsec-live's own usage
        log (see TestAdapterParsecUsageLog below), not from result.json's
        cost_usd/tokens — ParsecAgent never populates those (its real LLM
        calls happen inside the external parsec-live process, entirely
        outside Harbor's own agent-invocation metering). A missing/no-match
        log must degrade to 0, not silently fall back to result.json's
        null/wrong fields — that silent fallback was the original bug.
        """
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
            with tempfile.TemporaryDirectory() as log_dir_s:
                missing_log = Path(log_dir_s) / "no-such-parsec-live.log"
                with patch.dict(
                    os.environ,
                    {"TASK_ID": KNOWN_TASK_ID, "PARSEC_LIVE_LOG": str(missing_log)},
                    clear=True,
                ):
                    a = adapter_mod.Adapter()
                    task = a.tasks("val")[0]
                    with patch.object(
                        adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                    ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                        rollout = a.run_target(task, ctx=None)
            self.assertIsNone(rollout.error)
            self.assertEqual(rollout.cost_usd, 0.0)
            self.assertEqual(rollout.tokens, 0)
            tr = rollout.metadata["trial_result"]
            self.assertEqual(
                tr["cost_usd"], 1.37,
                "result.json's own (unused-for-rollout) field is still kept for reference",
            )
        finally:
            for d in created_trial_dirs:
                shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_run_target_reads_cost_and_tokens_from_the_parsec_live_log(self):
        """The real fix: cost/tokens come from parsec-live's own MetricsCollector
        log, matched to this trial by the timestamp window run_target() captures
        around its one harbor subprocess call.
        """
        created_trial_dirs: list[Path] = []
        with tempfile.TemporaryDirectory() as log_dir_s:
            log_path = Path(log_dir_s) / "parsec-live.log"

            def fake_run(cmd, **kwargs):
                if cmd[0] != "harbor":
                    return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")
                trial_dir = Path(cmd[3]).parent
                created_trial_dirs.append(trial_dir)
                trial_sub = trial_dir / "2026-09-18__09-17-39" / "bench-v4-icinga-011__zz"
                (trial_sub / "verifier").mkdir(parents=True)
                (trial_sub / "verifier" / "reward.json").write_text(json.dumps({"reward": 1.0}))
                (trial_sub / "config.json").write_text(json.dumps({"task": {"name": KNOWN_TASK_ID}}))
                (trial_sub / "result.json").write_text(json.dumps({}))
                # Written "live" during the harbor call itself, so its
                # timestamp always falls inside run_target()'s usage-window
                # capture regardless of how slow this test process is.
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                log_path.write_text(
                    f"{ts} INFO src.metrics.collector — usage runtime=legacy agent=icinga "
                    "in=34455 out=1145 cache_read=0 cache_write=0 cache_hit=0.0% tools=6 "
                    "errors=1 cost_usd=0.1205 latency_ms=123041\n"
                )
                return subprocess.CompletedProcess(cmd, 0)

            try:
                with patch.dict(
                    os.environ,
                    {"TASK_ID": KNOWN_TASK_ID, "PARSEC_LIVE_LOG": str(log_path)},
                    clear=True,
                ):
                    a = adapter_mod.Adapter()
                    task = a.tasks("val")[0]
                    with patch.object(
                        adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                    ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                        rollout = a.run_target(task, ctx=None)
                self.assertIsNone(rollout.error)
                self.assertAlmostEqual(rollout.cost_usd, 0.1205)
                self.assertEqual(rollout.tokens, 34455 + 1145)
                self.assertIn("parsec_usage_window", rollout.metadata)
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
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

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_a_hung_or_unlaunchable_seed_is_also_an_infra_error(self):
        """A 120s hang, or a missing install_seeds.py, must come back as
        Rollout.error like every other infra failure in run_target — not escape
        as an exception the caller has to guess the meaning of."""
        for exc in (
            subprocess.TimeoutExpired(cmd=["install_seeds.py"], timeout=120),
            OSError("No such file or directory: install_seeds.py"),
        ):
            with self.subTest(exc=type(exc).__name__):
                with patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True):
                    a = adapter_mod.Adapter()
                    task = a.tasks("val")[0]
                    with patch.object(
                        adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                    ), patch.object(adapter_mod.subprocess, "run", side_effect=exc):
                        rollout = a.run_target(task, ctx=None)
                self.assertIsNotNone(rollout.error)
                self.assertIn("install_seeds", rollout.error)
                score = a.score(task, rollout)
                self.assertEqual(score.reward, 0.0)
                self.assertIn("install_seeds", score.feedback)


class TestAdapterTrajectories(unittest.TestCase):
    """trajectories() is the directory cap-evolve copies verbatim into the
    optimizer's ./trajectories/, so it must point at the newest trial's whole
    harbor JOB dir (agent/ AND verifier/ output), and "newest" must be resolved
    numerically: a lexicographic sort puts "seed-10" before "seed-2", so the
    tenth trial's trajectory would be silently discarded as soon as num_trials
    exceeded 10.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs_root = Path(self.tmp.name) / "jobs"
        self.env_patch = patch.dict(os.environ, {"TASK_ID": KNOWN_TASK_ID}, clear=True)
        self.env_patch.start()
        # JOBS_ROOT is a module-level constant read at CALL time, so patching the
        # module attribute keeps this test entirely inside its own tmpdir instead
        # of writing fixtures into the real shared _run/jobs tree.
        self.jobs_patch = patch.object(adapter_mod, "JOBS_ROOT", self.jobs_root)
        self.jobs_patch.start()

    def tearDown(self):
        self.jobs_patch.stop()
        self.env_patch.stop()
        self.tmp.cleanup()

    def _make_trial(self, seed: int, millis: str, harbor_ts: str = "2026-09-18__09-17-39") -> Path:
        job_dir = self.jobs_root / KNOWN_TASK_ID / f"seed-{seed}" / millis / harbor_ts
        trial_sub = job_dir / "bench-v4-icinga-011__zz"
        (trial_sub / "agent").mkdir(parents=True)
        (trial_sub / "verifier").mkdir(parents=True)
        (trial_sub / "agent" / "trajectory.json").write_text("[]")
        (trial_sub / "verifier" / "reward.json").write_text(json.dumps({"reward": 0.5}))
        return job_dir

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_returns_none_when_nothing_has_run(self):
        a = adapter_mod.Adapter()
        self.assertIsNone(a.trajectories("val"))

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_returns_the_job_dir_not_one_trials_agent_dir(self):
        job_dir = self._make_trial(0, "1789740746891")
        a = adapter_mod.Adapter()
        got = a.trajectories("val")
        self.assertEqual(got, job_dir)
        self.assertNotEqual(got.name, "agent")
        # The job dir is what parse_job_dir() consumes: its children are trial
        # dirs carrying BOTH agent/ and verifier/.
        self.assertTrue(any((child / "verifier").is_dir() for child in got.iterdir()))
        self.assertTrue(any((child / "agent").is_dir() for child in got.iterdir()))

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_seed_10_sorts_after_seed_2(self):
        self._make_trial(2, "1789740746891")
        expected = self._make_trial(10, "1789740746000")  # EARLIER millis, higher seed
        a = adapter_mod.Adapter()
        self.assertEqual(
            a.trajectories("val"), expected,
            "seed-10 must sort after seed-2; a lexicographic sort gets this backwards",
        )

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_latest_millis_wins_within_one_seed(self):
        self._make_trial(3, "1789740746000")
        expected = self._make_trial(3, "1789740999999")
        a = adapter_mod.Adapter()
        self.assertEqual(a.trajectories("val"), expected)


class TestAdapterPythonPath(unittest.TestCase):
    """`harbor run` needs "." on PYTHONPATH to import parsec_harbor_agent from
    V4N, but clobbering the variable outright drops whatever the caller's
    environment (or the `cap-evolve run` parent process) already put there.
    """

    def _captured_env(self, initial_pythonpath: str | None) -> dict:
        captured: dict = {}
        created: list[Path] = []

        def fake_run(cmd, **kwargs):
            if cmd[0] != "harbor":
                return subprocess.CompletedProcess(cmd, 0, stdout="seeded", stderr="")
            captured.update(kwargs.get("env") or {})
            trial_dir = Path(cmd[3]).parent
            created.append(trial_dir)
            trial_sub = trial_dir / "2026-09-18__09-17-39" / "bench-v4-icinga-011__zz"
            (trial_sub / "verifier").mkdir(parents=True)
            (trial_sub / "verifier" / "reward.json").write_text(json.dumps({"reward": 1.0}))
            (trial_sub / "config.json").write_text(json.dumps({"task": {"name": KNOWN_TASK_ID}}))
            return subprocess.CompletedProcess(cmd, 0)

        base = {"TASK_ID": KNOWN_TASK_ID}
        if initial_pythonpath is not None:
            base["PYTHONPATH"] = initial_pythonpath
        try:
            with patch.dict(os.environ, base, clear=True):
                a = adapter_mod.Adapter()
                task = a.tasks("val")[0]
                with patch.object(
                    adapter_mod, "_resolve_docker_host", return_value="unix:///tmp/fake.sock"
                ), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run):
                    a.run_target(task, ctx=None)
        finally:
            for d in created:
                shutil.rmtree(d, ignore_errors=True)
        return captured

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_prepends_dot_and_keeps_an_existing_pythonpath(self):
        env = self._captured_env("/some/caller/path")
        self.assertEqual(env["PYTHONPATH"], "." + os.pathsep + "/some/caller/path")

    @unittest.skipUnless(_REAL_TASKS_DIR_PRESENT, "real bench-v4 tasks dir not present (set PARSEC_V4N)")
    def test_is_exactly_dot_when_nothing_was_set(self):
        env = self._captured_env(None)
        self.assertEqual(env["PYTHONPATH"], ".")


class TestParsecUsageLineParsing(unittest.TestCase):
    """Ground truth: this exact line was cross-referenced during the original
    investigation against the one real Harbor trial it belongs to —
    result.json's agent_execution.finished_at (2026-09-18T06:52:47.751114Z
    UTC) matches this line's local timestamp (09:52:47,746) to the second,
    local = UTC+3 on the machine that produced it. The parser must reproduce
    cost_usd=0.1205 and tokens=34455+1145 from it exactly.
    """

    REAL_LINE = (
        "2026-09-18 09:52:47,746 INFO src.metrics.collector — usage runtime=legacy "
        "agent=icinga in=34455 out=1145 cache_read=0 cache_write=0 cache_hit=0.0% "
        "tools=6 errors=1 cost_usd=0.1205 latency_ms=123041"
    )

    def test_parses_the_real_ground_truth_line(self):
        parsed = adapter_mod._parse_usage_line(self.REAL_LINE)
        self.assertIsNotNone(parsed)
        ts_utc, cost_usd, tokens = parsed
        self.assertAlmostEqual(cost_usd, 0.1205)
        self.assertEqual(tokens, 34455 + 1145 + 0 + 0)
        self.assertEqual(
            ts_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "2026-09-18 09:52:47",
        )

    def test_non_usage_line_does_not_match(self):
        self.assertIsNone(adapter_mod._parse_usage_line(
            "2026-09-18 09:52:47,746 INFO some.other.module — unrelated log line"
        ))

    def test_blank_and_malformed_lines_do_not_match(self):
        for line in ("", "\n", "not a log line at all", "usage runtime=legacy agent=icinga"):
            self.assertIsNone(adapter_mod._parse_usage_line(line))


class TestReadParsecUsageCost(unittest.TestCase):
    REAL_LINE = TestParsecUsageLineParsing.REAL_LINE

    def test_sums_matches_within_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "parsec-live.log"
            log_path.write_text(self.REAL_LINE + "\n")
            ts_utc, _, _ = adapter_mod._parse_usage_line(self.REAL_LINE)
            cost, tokens = adapter_mod._read_parsec_usage_cost(log_path, ts_utc, ts_utc)
            self.assertAlmostEqual(cost, 0.1205)
            self.assertEqual(tokens, 35600)

    def test_sums_two_matching_lines_rather_than_only_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "parsec-live.log"
            log_path.write_text(self.REAL_LINE + "\n" + self.REAL_LINE + "\n")
            ts_utc, _, _ = adapter_mod._parse_usage_line(self.REAL_LINE)
            cost, tokens = adapter_mod._read_parsec_usage_cost(log_path, ts_utc, ts_utc)
            self.assertAlmostEqual(cost, 0.1205 * 2)
            self.assertEqual(tokens, 35600 * 2)

    def test_ignores_lines_outside_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "parsec-live.log"
            log_path.write_text(self.REAL_LINE + "\n")
            ts_utc, _, _ = adapter_mod._parse_usage_line(self.REAL_LINE)
            far_start = ts_utc + timedelta(hours=1)
            far_end = ts_utc + timedelta(hours=2)
            cost, tokens = adapter_mod._read_parsec_usage_cost(log_path, far_start, far_end)
            self.assertEqual((cost, tokens), (0.0, 0))

    def test_returns_zero_when_log_file_is_missing(self):
        now = datetime.now(timezone.utc)
        cost, tokens = adapter_mod._read_parsec_usage_cost(
            Path("/tmp/definitely-not-a-real-parsec-live-log.log"), now, now,
        )
        self.assertEqual((cost, tokens), (0.0, 0))


if __name__ == "__main__":
    unittest.main()
