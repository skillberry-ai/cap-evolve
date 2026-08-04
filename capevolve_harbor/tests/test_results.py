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
    reward, rj = _read_reward(tmp_path)
    assert reward == 0.9


def test_read_reward_zero_is_honoured(tmp_path):
    """A legitimate 0.0 in reward.json must NOT trigger reward.txt fallback."""
    (tmp_path / "reward.json").write_text(json.dumps({"reward": 0.0}))
    (tmp_path / "reward.txt").write_text("0.99")
    reward, _ = _read_reward(tmp_path)
    assert reward == 0.0


def test_read_reward_falls_back_to_txt_when_json_absent(tmp_path):
    (tmp_path / "reward.txt").write_text("0.42")
    reward, _ = _read_reward(tmp_path)
    assert reward == 0.42


def test_read_reward_falls_back_to_txt_when_json_has_no_reward_key(tmp_path):
    (tmp_path / "reward.json").write_text(json.dumps({"accuracy": 0.8}))
    (tmp_path / "reward.txt").write_text("0.33")
    reward, _ = _read_reward(tmp_path)
    assert reward == 0.33


def test_read_reward_falls_back_to_txt_when_json_malformed(tmp_path):
    (tmp_path / "reward.json").write_text("not json at all")
    (tmp_path / "reward.txt").write_text("0.5")
    reward, _ = _read_reward(tmp_path)
    assert reward == 0.5


def test_read_reward_returns_zero_when_nothing_exists(tmp_path):
    reward, rj = _read_reward(tmp_path)
    assert reward == 0.0
    assert rj == {}


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
