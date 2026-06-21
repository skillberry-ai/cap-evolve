"""The optimizer is handed full trajectories + capability guidance in its workdir,
and the per-iteration INSTRUCTIONS.md is rendered from the template (no leftover
placeholders). The injected read-context is excluded from the candidate snapshot."""

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_CORE", str(CORE))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(EXAMPLE))
    monkeypatch.setenv("CAPEVOLVE_MOCK_SCRIPT", str(EXAMPLE / "mock_script.json"))


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_ctx", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def test_focus_instructions_render_from_template():
    """The shipped template renders with every placeholder substituted."""
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult

    cur = SplitResult.from_dict({
        "reward": 0.5, "stderr": 0.1,
        "per_task": [{"task_id": "a", "reward": 0.0, "feedback": "missed step"},
                     {"task_id": "b", "reward": 1.0, "feedback": "ok"}],
    })
    text = harness._focus_instructions(cur, None, "whole train set",
                                       capabilities=["tools"], algorithm="hill-climb",
                                       bench_repo="/tmp/somebench")
    assert "{{" not in text and "}}" not in text          # nothing left unrendered
    assert "./trajectories/" in text                       # read-pointer present
    assert "/tmp/somebench" in text                        # bench repo surfaced
    assert "code" in text.lower()                          # code-bearing-tools guidance


def test_injects_trajectories_and_guidance_then_excludes_from_snapshot(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    from cap_evolve import Budget, RunDir, harness

    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ctx", budget=Budget(max_iterations=2, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=2, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb", capabilities=["system-prompt"],
    )

    workdir = run_dir.root / "work" / "cand_0001"
    # the optimizer's working dir got the full trajectories + capability guidance + a
    # rendered prompt with no leftover placeholders
    assert (workdir / "trajectories").is_dir()
    assert any((workdir / "trajectories").iterdir())
    assert (workdir / "guidance" / "system-prompt" / "SKILL.md").exists()
    instr = (workdir / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "{{" not in instr

    # every candidate is snapshotted (accepted AND rejected), but the injected
    # read-context is NOT stored as part of the candidate
    snap = run_dir.candidate_dir("cand_0001")
    assert snap.exists()
    assert not (snap / "trajectories").exists()
    assert not (snap / "guidance").exists()
