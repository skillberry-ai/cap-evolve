"""Tests for capevolve_harbor.results — reward parsing and job dir walking."""
import json
import pytest
from pathlib import Path

from capevolve_harbor.results import parse_job_dir, build_feedback, _read_reward, TrialResult


@pytest.fixture
def job_dir(tmp_path):
    """Build a minimal Harbor job directory with two trials."""
    # Trial 1: reward.json with explicit reward key
    t1 = tmp_path / "trial-001"
    v1 = t1 / "verifier"
    v1.mkdir(parents=True)
    (v1 / "reward.json").write_text(json.dumps({"reward": 0.75, "accuracy": 0.8}))
    (v1 / "test-stdout.txt").write_text("All tests passed")
    (v1 / "test-stderr.txt").write_text("")
    a1 = t1 / "agent"
    a1.mkdir()
    (a1 / "trajectory.json").write_text(json.dumps({"steps": []}))
    cfg1 = t1 / "config.json"
    cfg1.write_text(json.dumps({"task": {"name": "task-001"}}))
    (t1 / "result.json").write_text(json.dumps({"cost_usd": 1.5, "tokens": 5000}))

    # Trial 2: reward.json with reward=0.0 (legitimate zero)
    t2 = tmp_path / "trial-002"
    v2 = t2 / "verifier"
    v2.mkdir(parents=True)
    (v2 / "reward.json").write_text(json.dumps({"reward": 0.0}))
    (v2 / "reward.txt").write_text("0.5")  # should NOT be used
    cfg2 = t2 / "config.json"
    cfg2.write_text(json.dumps({"task": {"name": "task-002"}}))

    return tmp_path


def test_parse_job_dir_finds_trials(job_dir):
    results = parse_job_dir(job_dir)
    assert "task-001" in results
    assert "task-002" in results
    assert len(results["task-001"]) == 1
    assert len(results["task-002"]) == 1


def test_parse_job_dir_reads_reward(job_dir):
    results = parse_job_dir(job_dir)
    assert results["task-001"][0].reward == 0.75
    assert results["task-001"][0].reward_json == {"reward": 0.75, "accuracy": 0.8}


def test_parse_job_dir_reads_cost_tokens(job_dir):
    results = parse_job_dir(job_dir)
    assert results["task-001"][0].cost_usd == 1.5
    assert results["task-001"][0].tokens == 5000


def test_parse_job_dir_reads_trajectory(job_dir):
    results = parse_job_dir(job_dir)
    assert results["task-001"][0].trajectory == {"steps": []}


def test_parse_job_dir_reads_verifier_stdout(job_dir):
    results = parse_job_dir(job_dir)
    assert results["task-001"][0].verifier_stdout == "All tests passed"


def test_parse_job_dir_filters_by_task_ids(job_dir):
    results = parse_job_dir(job_dir, task_ids=["task-001"])
    assert "task-001" in results
    assert "task-002" not in results


def test_parse_job_dir_skips_non_dirs(job_dir):
    (job_dir / "config.json").write_text("{}")
    (job_dir / "result.json").write_text("{}")
    results = parse_job_dir(job_dir)
    assert "config.json" not in results
    assert "result.json" not in results


def test_parse_job_dir_empty(tmp_path):
    results = parse_job_dir(tmp_path)
    assert results == {}


def test_parse_job_dir_nonexistent(tmp_path):
    results = parse_job_dir(tmp_path / "does_not_exist")
    assert results == {}


# --- _read_reward tests (the bug the review caught) ---

def test_read_reward_from_json_key(tmp_path):
    (tmp_path / "reward.json").write_text(json.dumps({"reward": 0.9}))
    reward, _, scored = _read_reward(tmp_path)
    assert reward == 0.9
    assert scored is True


def test_read_reward_zero_is_honoured(tmp_path):
    """A legitimate 0.0 in reward.json must NOT trigger reward.txt fallback."""
    (tmp_path / "reward.json").write_text(json.dumps({"reward": 0.0}))
    (tmp_path / "reward.txt").write_text("0.99")
    reward, _, scored = _read_reward(tmp_path)
    assert reward == 0.0
    assert scored is True


def test_read_reward_falls_back_to_txt_when_json_absent(tmp_path):
    (tmp_path / "reward.txt").write_text("0.42")
    reward, _, scored = _read_reward(tmp_path)
    assert reward == 0.42
    assert scored is True


def test_read_reward_falls_back_to_txt_when_json_has_no_reward_key(tmp_path):
    (tmp_path / "reward.json").write_text(json.dumps({"accuracy": 0.8}))
    (tmp_path / "reward.txt").write_text("0.33")
    reward, _, scored = _read_reward(tmp_path)
    assert reward == 0.33
    assert scored is True


def test_read_reward_falls_back_to_txt_when_json_malformed(tmp_path):
    (tmp_path / "reward.json").write_text("not json at all")
    (tmp_path / "reward.txt").write_text("0.5")
    reward, _, scored = _read_reward(tmp_path)
    assert reward == 0.5
    assert scored is True


def test_read_reward_returns_zero_when_nothing_exists(tmp_path):
    reward, rj, scored = _read_reward(tmp_path)
    assert reward == 0.0
    assert rj == {}
    assert scored is False, "an absent reward file is missing data, not a 0.0"


# --- build_feedback tests ---

def test_feedback_solved():
    tr = TrialResult(task_id="t1", reward=1.0)
    assert "fully solved" in build_feedback(tr)


def test_feedback_partial():
    tr = TrialResult(task_id="t1", reward=0.5)
    assert "Partial" in build_feedback(tr)


def test_feedback_zero():
    tr = TrialResult(task_id="t1", reward=0.0)
    assert "not solved" in build_feedback(tr)


def test_feedback_includes_metrics():
    tr = TrialResult(task_id="t1", reward=0.5, reward_json={"reward": 0.5, "accuracy": 0.8})
    fb = build_feedback(tr)
    assert "accuracy=0.8" in fb


def test_feedback_includes_error():
    tr = TrialResult(task_id="t1", reward=0.0, error="timeout")
    assert "timeout" in build_feedback(tr)


# --- infra-error detection tests -------------------------------------------
#
# A trial that crashed before the verifier ran has no reward file at all. Left
# undetected it reads as a legitimate "reward 0.0", which is how a Docker Hub
# 429 storm silently became a val score of 0.000 for two whole iterations.

_DOCKER_429 = (
    "Docker compose command failed for environment django__django-10554. "
    "Return code: 1. Stdout: #3 ERROR: unexpected status from HEAD request to "
    "https://registry-1.docker.io/v2/swebench/sweb.eval.x86_64.django_1776_"
    "django-10554/manifests/latest: 429 Too Many Requests"
)


def _errored_trial(root: Path, name: str, task: str, *, structured=True, text=True):
    """A trial dir shaped like harbor leaves one behind when _prepare() raises."""
    t = root / name
    (t / "verifier").mkdir(parents=True)   # created but EMPTY — no reward file
    (t / "agent").mkdir()
    (t / "config.json").write_text(json.dumps({"task": {"name": task}}))
    result: dict = {"task_name": task, "agent_result": None, "verifier_result": None}
    if structured:
        result["exception_info"] = {
            "exception_type": "RuntimeError",
            "exception_message": _DOCKER_429,
            "exception_traceback": "Traceback (most recent call last):\n  ...\n",
            "occurred_at": "2026-08-05T21:42:30.793278",
        }
    (t / "result.json").write_text(json.dumps(result))
    if text:
        (t / "exception.txt").write_text(
            "Traceback (most recent call last):\n"
            '  File ".../trial.py", line 351, in run\n'
            f"RuntimeError: {_DOCKER_429}\n"
        )
    return t


def test_errored_trial_sets_error(tmp_path):
    _errored_trial(tmp_path, "trial-err", "task-err")
    tr = parse_job_dir(tmp_path)["task-err"][0]
    assert tr.error is not None
    assert "RuntimeError" in tr.error


def test_errored_trial_surfaces_the_actual_cause(tmp_path):
    """The error text must name the real cause so a human can grep for it."""
    _errored_trial(tmp_path, "trial-err", "task-err")
    tr = parse_job_dir(tmp_path)["task-err"][0]
    assert tr.error is not None
    assert "429" in tr.error


def test_errored_trial_falls_back_to_exception_txt(tmp_path):
    """result.json may be absent/partial; exception.txt alone is enough."""
    _errored_trial(tmp_path, "trial-err", "task-err", structured=False)
    tr = parse_job_dir(tmp_path)["task-err"][0]
    assert tr.error is not None
    assert "RuntimeError" in tr.error


def test_errored_trial_error_is_bounded(tmp_path):
    """Errors land in feedback and event logs — they must not be unbounded."""
    t = _errored_trial(tmp_path, "trial-err", "task-err")
    (t / "exception.txt").write_text("RuntimeError: " + "x" * 100_000)
    tr = parse_job_dir(tmp_path)["task-err"][0]
    assert tr.error is not None
    assert len(tr.error) <= 2000


def test_healthy_trial_has_no_error(job_dir):
    """Regression guard: a real 0.0 from the verifier is NOT an infra error."""
    results = parse_job_dir(job_dir)
    assert results["task-001"][0].error is None
    assert results["task-002"][0].error is None
    assert results["task-002"][0].reward == 0.0


def test_verifier_reward_wins_over_exception(tmp_path):
    """An exception AFTER the verifier scored is a hiccup, not a lost trial.

    The reward file is the authoritative signal that the trial produced a real
    score, so honour it rather than discarding a genuine measurement.
    """
    t = _errored_trial(tmp_path, "trial-late", "task-late")
    (t / "verifier" / "reward.json").write_text(json.dumps({"reward": 1.0}))
    tr = parse_job_dir(tmp_path)["task-late"][0]
    assert tr.reward == 1.0
    assert tr.error is None


def test_missing_verifier_dir_without_exception_is_an_error(tmp_path):
    """No reward AND no verifier output is not a measurement either."""
    t = tmp_path / "trial-bare"
    t.mkdir()
    (t / "config.json").write_text(json.dumps({"task": {"name": "task-bare"}}))
    tr = parse_job_dir(tmp_path)["task-bare"][0]
    assert tr.error is not None
