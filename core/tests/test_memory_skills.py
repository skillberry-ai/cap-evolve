"""The memory_skill plug-in interface (#400, #404): md-files stays the unchanged
default, and selecting wiki drives a real end-to-end run through the extracted
weakness-graph format instead of LEDGER/JOURNAL/INSIGHTS."""

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
    spec = importlib.util.spec_from_file_location("toy_calc_adapter3", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def test_resolve_memory_defaults_and_looks_up_by_name():
    from cap_evolve import harness

    assert isinstance(harness.resolve_memory(None), harness.MdFilesMemory)
    assert isinstance(harness.resolve_memory("md-files"), harness.MdFilesMemory)
    assert isinstance(harness.resolve_memory("wiki"), harness.WikiMemory)
    # An unknown name must never crash a run — it silently falls back to the default.
    assert isinstance(harness.resolve_memory("no-such-skill"), harness.MdFilesMemory)


def test_wiki_memory_skill_end_to_end(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    from cap_evolve import Budget, RunDir, harness

    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="wiki", budget=Budget(max_iterations=3, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    ctx = harness.OptimizerContext(memory_skill="wiki")
    summary = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=3, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="all-at-once", ctx=ctx,
    )
    assert summary["iterations"] >= 1

    # The wiki lives at the run root's ABSOLUTE path, not copied into any iteration's
    # working dir, and framework-owned LEDGER.md still gets built (facts are scheme-
    # agnostic) — but the md-files append-only journal/accumulators must NOT exist.
    assert (run_dir.root / "wiki" / "weaknesses").is_dir()
    assert (run_dir.root / "wiki" / "solutions").is_dir()
    assert (run_dir.root / "wiki" / "results").is_dir()
    work = run_dir.root / "work" / run_dir.best_id
    assert (work / "LEDGER.md").exists()
    assert not (work / "JOURNAL.md").exists()
    assert not (work / "INSIGHTS.md").exists()
    assert not (run_dir.root / "JOURNAL.md").exists()

    # The mock optimizer only appends to JOURNAL.md when the harness seeded one
    # (see _mock_apply.py) — under wiki it never gets seeded, so no candidate should
    # ever have been mis-escalated as an "empty handover" (a false positive that the
    # md-files-only pointer path would have produced before this was memory-aware).
    events = [e.get("kind") for e in _read_events(run_dir)]
    warnings = [e for e in _read_events(run_dir)
               if e.get("kind") == "optimizer_context_warning"
               and "empty handover" in str(e.get("error") or "")]
    assert warnings == []
    assert "step" in events


def _read_events(run_dir):
    import json
    if not run_dir.events_path.exists():
        return []
    out = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
