"""``objectives`` / ``gate_mode: pareto`` flow all the way from `capevolve.yaml` through
`cli.py`'s `run` command into hill-climb's `run.py` and its gate call (issue #684 item 8).

Mirrors `test_orchestration_mode.py`'s real toy_calc project + in-process `cli.main`
drive, so this exercises the actual argv `cli.py` builds for the algorithm subprocess
rather than a hand-rolled stand-in.
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
TEMPLATE_SPEC = REPO / "templates" / "project" / "capevolve.yaml"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _build_project(tmp_path: Path, *, gate_mode: str | None, objectives: list | None) -> Path:
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")

    spec_text = TEMPLATE_SPEC.read_text(encoding="utf-8")
    if gate_mode is not None:
        spec_text = spec_text.replace("gate_mode: paired", f"gate_mode: {gate_mode}")
    if objectives is not None:
        spec_text += "\nobjectives:\n" + "\n".join(
            f"  - {{name: {o['name']}, direction: {o['direction']}}}" for o in objectives
        ) + "\n"
    spec_path = project / "capevolve.yaml"
    spec_path.write_text(spec_text, encoding="utf-8")
    return spec_path


def _run_dir(tmp_path, run_ts) -> Path:
    return tmp_path / ".capevolve" / f"run_{run_ts}"


def _any_step_reason_has(run_dir: Path, needle: str) -> bool:
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    for line in events:
        rec = json.loads(line)
        if rec.get("kind") == "step" and needle in str(rec.get("reason", "")):
            return True
    return False


def test_gate_mode_pareto_with_no_objectives_runs_default_pair(tmp_path):
    """``gate_mode: pareto`` with no ``objectives:`` key -> hill-climb's gate call
    actually dispatches to pareto mode end-to-end (cap_evolve.gate's own default pair)."""
    from cap_evolve import cli

    spec_path = _build_project(tmp_path, gate_mode="pareto", objectives=None)
    rc = cli.main(["run", "--spec", str(spec_path),
                   "--project", str(tmp_path / ".capevolve" / "project"),
                   "--dashboard", "off", "--run-ts", "pareto1"])
    assert rc == 0

    run_dir = _run_dir(tmp_path, "pareto1")
    assert _any_step_reason_has(run_dir, "pareto"), (
        "expected at least one 'step' event whose gate reason names pareto mode")


def test_declared_single_objective_reward_only_still_runs_pareto_path(tmp_path):
    """A declared ``objectives:`` with only ``reward`` is forwarded verbatim (no cost
    needed, so no ParetoObjectiveError) -- confirms `cli.py` actually serializes the
    spec's objectives list into `--objectives` rather than always using the default."""
    from cap_evolve import cli

    spec_path = _build_project(
        tmp_path, gate_mode="pareto",
        objectives=[{"name": "reward", "direction": "maximize"}])
    rc = cli.main(["run", "--spec", str(spec_path),
                   "--project", str(tmp_path / ".capevolve" / "project"),
                   "--dashboard", "off", "--run-ts", "pareto2"])
    assert rc == 0

    run_dir = _run_dir(tmp_path, "pareto2")
    assert _any_step_reason_has(run_dir, "pareto")


def test_no_objectives_key_means_no_flag_forwarded(tmp_path):
    """Backward compat: a plain (non-pareto) spec with no ``objectives:`` key never gets
    an ``--objectives`` flag -- confirmed by the run completing exactly as it did before
    #684 (paired gate reasons, never a pareto one)."""
    from cap_evolve import cli

    spec_path = _build_project(tmp_path, gate_mode=None, objectives=None)
    rc = cli.main(["run", "--spec", str(spec_path),
                   "--project", str(tmp_path / ".capevolve" / "project"),
                   "--dashboard", "off", "--run-ts", "nopareto"])
    assert rc == 0

    run_dir = _run_dir(tmp_path, "nopareto")
    assert not _any_step_reason_has(run_dir, "pareto")
