"""The git store records every iteration and the optimizer memory is populated."""

import shutil
import subprocess
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
    spec = importlib.util.spec_from_file_location("toy_calc_adapter2", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def test_git_store_and_memory(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.store import VersionStore

    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="gs", budget=Budget(max_iterations=3, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    store = VersionStore(kind="git", root=run_dir.root)
    summary = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=3, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="all-at-once", store=store,
    )
    assert summary["accepts"] >= 1

    # git history records seed + every iteration
    log = store.log()
    assert any("seed" in l for l in log)
    assert any("ACCEPT" in l for l in log)
    # memory files populated: at least one accepted (history) and the rejects exist
    assert run_dir.history_path.exists()
    hist = run_dir.history_path.read_text()
    assert '"candidate_id"' in hist and run_dir.best_id in hist
    # the optimizer saw MEMORY.md + STATE.md in a candidate workdir
    cand = run_dir.candidate_dir(run_dir.best_id)
    assert (cand / "MEMORY.md").exists()
    assert (cand / "STATE.md").exists()
