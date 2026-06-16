"""Extensibility proof: a brand-new benchmark (json_extract) works from scratch.

Only an adapter + data + seed prompt were added — no core or skill changes. The
same harness/skills produce a real, gate-accepted improvement, and the test is
sealed. This is the "works for a new benchmark from scratch" guarantee in CI.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "json_extract"
MOCK_RUN = REPO / "skills" / "optimizers" / "mock" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_JSON_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _load_adapter(py_file: Path, mod_name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(mod_name, py_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


def test_new_benchmark_from_scratch(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    adapter = _load_adapter(EXAMPLE / "adapter.py", "json_extract_adapter")

    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="jx", budget=Budget(max_iterations=3, stall=2))

    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base.reward == 0.0, "seed prompt lacks [STRICT_JSON]; baseline must fail JSON scoring"

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--workdir", "{workdir}", "--prompt", "{prompt}"])
    summary = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=3, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="all-at-once",
    )
    assert summary["accepts"] >= 1
    assert summary["best_val"] == 1.0

    best_dir = run_dir.candidate_dir(run_dir.best_id)
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir)
    assert payload["test"]["reward"] == 1.0
