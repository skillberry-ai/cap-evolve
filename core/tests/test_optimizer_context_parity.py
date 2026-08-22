"""EVERY algorithm receives the SAME optimizer context — the guard for issue #109.

`docs/ARCHITECTURE.md` ("What the optimizer receives each iteration") describes a
property of the harness, not of hill-climb. Before this test, hill-climb was the only
algorithm that got the full context: gepa never injected any of it and skillopt called
the prompt renderer bare (no capability brief, no template, no bench repo — and a
PARALLEL_NOTE that actively told a parallel-capable optimizer it was sequential).

So the assertions below are parametrized over ALL algorithms, driving one real iteration
of each with the mock (zero-API) optimizer on toy_calc and checking the assembled
optimizer working dir + rendered prompt piece by piece. A newly added algorithm that
forgets to thread ``harness.OptimizerContext`` fails here loudly instead of silently
running blind.
"""

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

ALGORITHMS = ("hill-climb", "gepa", "skillopt")
# A parallel-capable optimizer row: exercises the features reference, the native skills
# dir and the {{PARALLEL_NOTE}} that skillopt used to get wrong.
OPTIMIZER_NAME = "claude-code"
CAPABILITY = "system-prompt"
SOURCE_FILE = "adapter.py"          # a real file under the toy project dir
BENCH_REPO = "/tmp/some-bench-repo"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_CORE", str(CORE))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(EXAMPLE))
    monkeypatch.setenv("CAPEVOLVE_MOCK_SCRIPT", str(EXAMPLE / "mock_script.json"))


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter_parity", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def _run_one_iteration(algorithm: str, tmp_path: Path) -> Path:
    """Run ONE iteration of ``algorithm`` with the shared context; return its workdir."""
    from cap_evolve import Budget, RunDir, gepa, harness, skillopt

    adapter = _toy_adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="parity",
                            budget=Budget(max_iterations=1, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    ctx = harness.OptimizerContext(
        capabilities=(CAPABILITY,), optimizer_name=OPTIMIZER_NAME,
        capability_sources=(SOURCE_FILE,), project_dir=EXAMPLE, bench_repo=BENCH_REPO)
    common = dict(run_dir=run_dir, optimizer=optimizer, ctx=ctx,
                  gate_kwargs={"mode": "significant", "k_se": 1.0})

    if algorithm == "hill-climb":
        harness.hill_climb_loop(adapter, current_val=base, focus="all", max_iterations=1,
                                algorithm="hill-climb", **common)
    elif algorithm == "gepa":
        gepa.gepa_loop(adapter, seed_val=base, max_iterations=1, minibatch_size=2, **common)
    elif algorithm == "skillopt":
        skillopt.skillopt_loop(adapter, current_val=base, epochs=1, batch_size=2,
                               slow_update=False, algorithm="skillopt", **common)
    else:  # pragma: no cover - guard for a future algorithm added to ALGORITHMS
        raise AssertionError(f"no driver for {algorithm}")

    workdirs = sorted(p for p in (run_dir.root / "work").iterdir() if p.is_dir())
    assert workdirs, f"{algorithm} produced no iteration workdir"
    return workdirs[0]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_every_algorithm_gets_the_same_optimizer_context(algorithm, tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    workdir = _run_one_iteration(algorithm, tmp_path)

    # 1) the parent step's verbatim trajectories
    assert (workdir / "trajectories").is_dir(), f"{algorithm}: no ./trajectories/"
    assert any((workdir / "trajectories").iterdir()), f"{algorithm}: empty ./trajectories/"

    # 2) the selected capability skill — as guidance AND placed natively for the agent
    assert (workdir / "guidance" / CAPABILITY / "SKILL.md").exists(), \
        f"{algorithm}: no ./guidance/{CAPABILITY}/"
    assert (workdir / ".claude" / "skills" / CAPABILITY / "SKILL.md").exists(), \
        f"{algorithm}: capability skill not placed natively"

    # 3) the diagnose method (failure clustering)
    assert (workdir / "guidance" / "diagnose" / "SKILL.md").exists(), \
        f"{algorithm}: no ./guidance/diagnose/"

    # 4) supporting sources / data model
    assert (workdir / "guidance" / "sources" / SOURCE_FILE).exists(), \
        f"{algorithm}: no ./guidance/sources/{SOURCE_FILE}"

    # 5) the resolved optimizer's own features reference
    assert (workdir / "guidance" / "optimizer" / f"{OPTIMIZER_NAME}.md").exists(), \
        f"{algorithm}: no ./guidance/optimizer/{OPTIMIZER_NAME}.md"

    # 6) per-task IMPACT of prior candidates + the protect-set
    for name in ("LEDGER.md", "JOURNAL.md", "RUNMAP.md"):
        assert (workdir / name).exists(), f"{algorithm}: no ./{name}"

    # 7) the prompt itself: rendered from the shared template, with the capability brief,
    # the bench-repo pointer and a PARALLEL note that matches the real optimizer.
    instr = (workdir / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "{{" not in instr, f"{algorithm}: unrendered placeholder in the prompt"
    assert BENCH_REPO in instr, f"{algorithm}: bench repo not surfaced"
    assert CAPABILITY in instr, f"{algorithm}: no capability brief"
    assert "fan out" in instr.lower(), \
        f"{algorithm}: parallel-capable optimizer not told it can fan out"


def test_injected_context_is_not_part_of_the_candidate():
    """The injected read-context must never be hashed, diffed or optimized as capability
    content — otherwise gepa's eval cache misses every iteration and its component
    selector 'edits' the guidance we just handed it."""
    from cap_evolve.types import NON_CAPABILITY_DIRS

    for d in ("trajectories", "guidance", ".claude", "prior_iterations"):
        assert d in NON_CAPABILITY_DIRS
