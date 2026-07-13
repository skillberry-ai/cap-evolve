"""Tests for starting optimization with an empty seed capability.

Verifies that every capability type (system-prompt, skill-package, tools,
mcp-tool) accepts an empty directory as a valid starting state, and that the
harness baseline/optimizer-instructions flow handles the empty seed correctly.
"""

import json
import shutil
from pathlib import Path

import pytest

from cap_evolve import Budget, RunDir, harness
from cap_evolve.loop import SplitResult


# ---- capability validate: empty dirs return ok=True -----------------------

def test_system_prompt_validate_empty(tmp_path):
    """system-prompt validate returns ok=True for an empty directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sp_abstract",
        Path(__file__).resolve().parents[2] / "skills" / "capabilities" / "system-prompt" / "scripts" / "abstract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.validate(tmp_path)
    assert result["ok"] is True
    assert result.get("empty") is True
    assert result["problems"] == []


def test_system_prompt_validate_nonempty(tmp_path):
    """system-prompt validate still works for a non-empty directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sp_abstract",
        Path(__file__).resolve().parents[2] / "skills" / "capabilities" / "system-prompt" / "scripts" / "abstract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "prompt.txt").write_text("Hello world", encoding="utf-8")
    result = mod.validate(tmp_path)
    assert result["ok"] is True
    assert "empty" not in result or result.get("empty") is not True


def test_system_prompt_is_empty(tmp_path):
    """system-prompt is_empty detects empty vs non-empty directories."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sp_abstract",
        Path(__file__).resolve().parents[2] / "skills" / "capabilities" / "system-prompt" / "scripts" / "abstract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_empty(tmp_path) is True
    (tmp_path / "prompt.txt").write_text("Hello", encoding="utf-8")
    assert mod.is_empty(tmp_path) is False


def test_tool_surface_validate_empty(tmp_path):
    """tool_surface validate returns ok=True for an empty directory."""
    from cap_evolve import tool_surface
    result = tool_surface.validate(tmp_path)
    assert result["ok"] is True
    assert result.get("empty") is True
    assert result["problems"] == []


def test_tool_surface_validate_nonempty(tmp_path):
    """tool_surface validate still works for a directory with tools."""
    from cap_evolve import tool_surface
    tools_data = {"tools": [{"name": "test-tool", "description": "A test tool", "parameters": {}}]}
    (tmp_path / "tools.json").write_text(json.dumps(tools_data), encoding="utf-8")
    result = tool_surface.validate(tmp_path)
    assert result["ok"] is True
    assert "empty" not in result or result.get("empty") is not True


def test_tool_surface_is_empty(tmp_path):
    """tool_surface is_empty detects empty vs non-empty directories."""
    from cap_evolve import tool_surface
    assert tool_surface.is_empty(tmp_path) is True
    tools_data = {"tools": [{"name": "t", "description": "d", "parameters": {}}]}
    (tmp_path / "tools.json").write_text(json.dumps(tools_data), encoding="utf-8")
    assert tool_surface.is_empty(tmp_path) is False


def test_skill_package_validate_empty(tmp_path):
    """skill-package validate returns ok=True for an empty directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sk_abstract",
        Path(__file__).resolve().parents[2] / "skills" / "capabilities" / "skill-package" / "scripts" / "abstract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.validate(tmp_path)
    assert result["ok"] is True
    assert result.get("empty") is True
    assert result["problems"] == []


def test_skill_package_is_empty(tmp_path):
    """skill-package is_empty detects empty vs non-empty directories."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sk_abstract",
        Path(__file__).resolve().parents[2] / "skills" / "capabilities" / "skill-package" / "scripts" / "abstract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_empty(tmp_path) is True
    (tmp_path / "SKILL.md").write_text(
        "---\nname: test\ndescription: Test. Use when needed.\n---\n# Test\n",
        encoding="utf-8",
    )
    assert mod.is_empty(tmp_path) is False


# ---- harness: baseline with empty seed -----------------------------------

def _toy_adapter():
    """A trivial adapter that returns 0 reward for any candidate."""
    from cap_evolve.adapter import CapabilityAdapter
    from cap_evolve.types import Task, Rollout, Score

    class EmptyAdapter(CapabilityAdapter):
        def tasks(self, split):
            return [Task(id=f"t{i}", input=f"input-{i}") for i in range(4)]
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output="empty", trace="empty trajectory")
        def score(self, task, rollout):
            return Score(task_id=task.id, reward=0.0, feedback="no capability provided")

    return EmptyAdapter()


def test_baseline_with_empty_seed(tmp_path):
    """baseline() works when the seed directory is empty."""
    adapter = _toy_adapter()
    seed = tmp_path / "empty_seed"
    seed.mkdir()
    # No files in seed dir

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="empty",
                            budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, run_dir, seed=0)
    result = harness.baseline(adapter, seed, run_dir=run_dir)

    # Should succeed with 0 reward (everything fails)
    assert result.reward == 0.0
    # The seed candidate should exist
    assert run_dir.candidate_dir("seed").is_dir()


def test_baseline_with_nonexistent_seed_dir(tmp_path):
    """baseline() creates the seed directory if it doesn't exist."""
    adapter = _toy_adapter()
    seed = tmp_path / "nonexistent_seed"
    # Don't create the directory

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="nodir",
                            budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, run_dir, seed=0)
    result = harness.baseline(adapter, seed, run_dir=run_dir)

    assert result.reward == 0.0
    assert seed.is_dir()


# ---- optimizer instructions: empty seed note ------------------------------

def test_empty_seed_note_when_all_failing():
    """_empty_seed_note returns guidance when all tasks are failing."""
    per_task = [
        {"task_id": "t0", "reward": 0.0, "feedback": "fail"},
        {"task_id": "t1", "reward": 0.0, "feedback": "fail"},
    ]
    current_val = SplitResult(split="val", reward=0.0, stderr=0.0, per_task=per_task,
                              seconds=0.0, cost_usd=0.0, tokens=0)
    note = harness._empty_seed_note(current_val)
    assert "EMPTY SEED" in note
    assert "create" in note.lower()


def test_empty_seed_note_not_shown_when_passing():
    """_empty_seed_note returns empty when some tasks pass."""
    per_task = [
        {"task_id": "t0", "reward": 1.0, "feedback": "pass"},
        {"task_id": "t1", "reward": 0.0, "feedback": "fail"},
    ]
    current_val = SplitResult(split="val", reward=0.5, stderr=0.1, per_task=per_task,
                              seconds=0.0, cost_usd=0.0, tokens=0)
    note = harness._empty_seed_note(current_val)
    assert note == ""


def test_empty_seed_note_not_shown_when_seed_nonempty_but_all_failing():
    """The false-positive guard: a genuinely hard, NON-empty seed that scores 0 on
    every task must NOT be told the directory is empty. The explicit seed_empty=False
    signal overrides the reward heuristic (which alone would wrongly fire here)."""
    per_task = [
        {"task_id": "t0", "reward": 0.0, "feedback": "fail"},
        {"task_id": "t1", "reward": 0.0, "feedback": "fail"},
    ]
    current_val = SplitResult(split="val", reward=0.0, stderr=0.0, per_task=per_task,
                              seconds=0.0, cost_usd=0.0, tokens=0)
    # Reward heuristic alone (seed_empty=None) would fire...
    assert "EMPTY SEED" in harness._empty_seed_note(current_val)
    # ...but the authoritative signal that the seed is NON-empty suppresses it.
    assert harness._empty_seed_note(current_val, seed_empty=False) == ""
    # ...and an authoritatively-empty seed still fires it.
    assert "EMPTY SEED" in harness._empty_seed_note(current_val, seed_empty=True)


def test_capability_is_empty_signal(tmp_path):
    """_capability_is_empty reflects the capability's own is_empty() on the dir."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert harness._capability_is_empty(["skill-package"], empty) is True
    (empty / "SKILL.md").write_text(
        "---\nname: x\ndescription: Do a thing. Use when needed.\n---\n# x\n",
        encoding="utf-8")
    assert harness._capability_is_empty(["skill-package"], empty) is False
    # No capabilities -> no signal (None => reward-heuristic fallback).
    assert harness._capability_is_empty([], empty) is None


# ---- end-to-end: empty seed through hill-climb loop ----------------------

def test_hill_climb_with_empty_seed(tmp_path):
    """A hill-climb loop can start from an empty seed directory."""
    if shutil.which("git") is None:
        pytest.skip("git not available")

    adapter = _toy_adapter()
    seed = tmp_path / "empty_seed"
    seed.mkdir()

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="hc_empty",
                            budget=Budget(max_iterations=1, stall=2))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base.reward == 0.0

    # A no-op optimizer: does nothing, so candidate == parent (rejected or same).
    def noop_optimizer(workdir, instructions):
        # Verify the instructions contain the empty seed note
        assert "EMPTY SEED" in instructions
        return None

    result = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=noop_optimizer, current_val=base,
        focus="all", max_iterations=1,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb",
    )
    assert result["iterations"] == 1
