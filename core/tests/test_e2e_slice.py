"""End-to-end proof slice — the whole pipeline, zero API cost, deterministic.

Drives the real toy_calc adapter and the real `mock` optimizer skill script
(via subprocess, exactly as a host would) through:
    cap-evolve check -> baseline -> all-at-once step -> finalize -> report-equivalent
and asserts the honesty guarantees hold. This is the CI gate that proves the
architecture works without any model.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))  # import the toy adapter


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def test_full_slice(tmp_path):
    from cap_evolve import Budget, RunDir, TestSealError, harness
    from cap_evolve.loop import SplitResult
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)

    adapter = toy.Adapter()

    # seed capability (copy so the loop can mutate copies, not the example)
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=5, stall=2))

    # baseline: splits frozen, seed scored on val
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base.reward == 0.0, "seed prompt lacks [CALC]; baseline must fail"

    # one optimize step using the REAL mock optimizer skill (subprocess)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"]
    )
    step = harness.run_step(
        adapter, run_dir=run_dir,
        parent_dir=run_dir.candidate_dir("seed"),
        optimizer=optimizer,
        instructions="improve val pass rate",
        current_val=base,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    assert step["accepted"] is True, "adding [CALC] should clear the significance gate"
    assert SplitResult.from_dict(step["candidate_val"]).reward == 1.0

    # finalize: test scored once
    best_dir = run_dir.candidate_dir(run_dir.best_id)
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir)
    assert payload["test"]["reward"] == 1.0

    # test is sealed: a second finalize must refuse
    with pytest.raises(TestSealError):
        harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir)


def test_cyclic_variant_also_improves(tmp_path):
    """The shared hill-climb loop works for a focus variant (cyclic), end to end."""
    from cap_evolve import RunDir, harness
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    adapter = toy.Adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="cyc",
                            budget=__import__("cap_evolve").Budget(max_iterations=5, stall=2))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    summary = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="cyclic", max_iterations=5, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="cyclic",
    )
    assert summary["accepts"] >= 1
    assert summary["best_val"] == 1.0


@pytest.mark.parametrize("focus", ["cyclic", "hardest-first"])
def test_narrow_focus_renders_the_focused_tasks_failures(tmp_path, focus):
    """A narrow focus must focus a task the loop actually HAS per-task data for.

    ``_focus_instructions`` filters the parent's VAL rows, so a focus set built from
    TRAIN ids intersected them in nothing and every non-``all`` schedule shipped a
    prompt with "0 failing of 0 tasks" and no failure index at all. Assert on the
    rendered prompt, not on a tuple of schedule names — the mock optimizer applies a
    fixed edit script and never reads the prompt, so only this can see the regression.
    """
    from cap_evolve import Budget, RunDir, harness
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    adapter = toy.Adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="f", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    seen = []

    def capturing(workdir, instructions):  # noqa: ARG001 — a no-op proposer
        seen.append(instructions)
        return None

    harness.hill_climb_loop(adapter, run_dir=run_dir, optimizer=capturing, current_val=base,
                            focus=focus, max_iterations=1)
    assert len(seen) == 1
    prompt = seen[0]
    val_ids = run_dir.read_splits().val
    assert any(f"Focus: task {t}." in prompt for t in val_ids), \
        "the focused task must be a VAL id — that is the only per-task data the loop holds"
    assert "## (a)" in prompt, "the focused task's failures must reach the optimizer"
    assert "0 failing of 0 tasks" not in prompt


def test_baseline_better_than_nothing_is_gated(tmp_path):
    """A no-op edit (no change) must be rejected by the significance gate."""
    from cap_evolve import RunDir, harness
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    adapter = toy.Adapter()
    seed = tmp_path / "seed"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t2")
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)

    noop = harness.optimizer_from_command(["python3", "-c", "import sys; sys.exit(0)"])
    step = harness.run_step(
        adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
        optimizer=noop, instructions="(no-op)", current_val=base,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
    )
    assert step["accepted"] is False
