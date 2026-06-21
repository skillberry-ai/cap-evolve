"""Native per-optimizer-agent skill injection: when the resolved optimizer row
declares a ``skills_dir`` / ``instructions_file``, the harness places the capability +
diagnose skills where that agent NATIVELY discovers them and writes a pointer into its
always-on instructions file — so headless runs load them reliably. Agents with no
``skills_dir`` (e.g. mock) are unaffected (only ./guidance/ is used)."""

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
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_native", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def _run_loop(tmp_path, *, optimizer_name):
    from cap_evolve import Budget, RunDir, harness

    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="native",
                            budget=Budget(max_iterations=1, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb", capabilities=["system-prompt"],
        optimizer_name=optimizer_name,
    )
    return run_dir


def test_claude_code_places_native_skills_and_instructions_pointer(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")

    run_dir = _run_loop(tmp_path, optimizer_name="claude-code")
    workdir = run_dir.root / "work" / "cand_0001"

    # capability skill copied into the agent's native skills dir
    assert (workdir / ".claude" / "skills" / "system-prompt" / "SKILL.md").exists()
    # the diagnose skill is placed natively too
    assert (workdir / ".claude" / "skills" / "diagnose" / "SKILL.md").exists()

    # the always-on instructions file got the generic pointer block
    claude_md = workdir / "CLAUDE.md"
    assert claude_md.exists()
    text = claude_md.read_text(encoding="utf-8")
    assert "INSTRUCTIONS.md" in text
    assert ".claude/skills" in text
    assert "MEMORY.md" in text and "STATE.md" in text

    # the ./guidance/ channel still works in parallel
    assert (workdir / "guidance" / "system-prompt" / "SKILL.md").exists()

    # native dirs/files are NOT stored in the candidate snapshot (capability-only)
    snap = run_dir.candidate_dir("cand_0001")
    assert snap.exists()
    assert not (snap / ".claude").exists()
    assert not (snap / "CLAUDE.md").exists()


def test_pointer_is_idempotent(tmp_path):
    """Writing the pointer twice does not duplicate the block."""
    from cap_evolve import harness

    p = tmp_path / "CLAUDE.md"
    harness._write_instructions_pointer(p, ".claude/skills")
    harness._write_instructions_pointer(p, ".claude/skills")
    assert p.read_text(encoding="utf-8").count(harness._NATIVE_POINTER_MARK) == 1


def test_mock_optimizer_has_no_native_placement(tmp_path):
    """An agent with no skills_dir (mock) gets only ./guidance/ — no native dirs."""
    if shutil.which("git") is None:
        pytest.skip("git not available")

    run_dir = _run_loop(tmp_path, optimizer_name="mock")
    workdir = run_dir.root / "work" / "cand_0001"

    assert (workdir / "guidance" / "system-prompt" / "SKILL.md").exists()
    assert not (workdir / ".claude").exists()
    assert not (workdir / "CLAUDE.md").exists()
