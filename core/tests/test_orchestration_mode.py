"""orchestration_mode routes cap-evolve run; deterministic path is unchanged.

Builds a real runnable toy_calc project (mirroring examples/toy_calc/run.sh) and
drives it through the actual `cap_evolve.cli` `run` command in-process:

  * agent mode  -> check + baseline, then a handoff JSON; algorithm + finalize skipped
  * deterministic mode -> the full pipeline still runs and seals the test (unchanged)
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


def _build_project(tmp_path: Path, orchestration_mode: str) -> tuple[Path, Path]:
    """Scaffold a runnable project exactly like examples/toy_calc/run.sh does.

    Returns (project_dir, spec_path). The workdir is tmp_path (the dir that holds
    .capevolve/), so `run_dir` printed by the run resolves under tmp_path.
    """
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")

    spec_text = TEMPLATE_SPEC.read_text(encoding="utf-8")
    spec_text = spec_text.replace(
        "orchestration_mode: deterministic", f"orchestration_mode: {orchestration_mode}"
    )
    assert f"orchestration_mode: {orchestration_mode}" in spec_text
    spec_path = project / "capevolve.yaml"
    spec_path.write_text(spec_text, encoding="utf-8")
    return project, spec_path


def _json_lines(out: str) -> list[dict]:
    objs = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            objs.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return objs


def test_plan_only_surfaces_mode(tmp_path, capsys):
    from cap_evolve import cli

    _, spec_path = _build_project(tmp_path, "agent")
    rc = cli.main(["run", "--spec", str(spec_path),
                   "--project", str(tmp_path / ".capevolve" / "project"),
                   "--dashboard", "off", "--plan-only"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["orchestration_mode"] == "agent"


def test_agent_mode_stops_after_baseline_with_handoff(tmp_path, capsys):
    from cap_evolve import cli

    project, spec_path = _build_project(tmp_path, "agent")
    rc = cli.main(["run", "--spec", str(spec_path), "--project", str(project),
                   "--dashboard", "off", "--run-ts", "agent"])
    assert rc == 0

    out = capsys.readouterr().out
    handoff = next((o for o in _json_lines(out) if o.get("mode") == "agent"), None)
    assert handoff is not None, f"no agent handoff JSON in output:\n{out}"
    assert handoff["run_dir"], "handoff must carry the run_dir"
    assert handoff["next"], "handoff must tell the agent what to do next"
    assert handoff["algorithm"] == "hill-climb"

    # baseline ran (run dir + splits exist) but the algorithm/finalize did NOT:
    # the test split is still sealed-unused.
    run_dir = tmp_path / handoff["run_dir"]
    splits = json.loads((run_dir / "splits.json").read_text(encoding="utf-8"))
    assert splits["test_used"] is False, "agent mode must not score/seal the test"


def test_deterministic_mode_still_runs_full_pipeline(tmp_path, capsys):
    """The same setup in deterministic mode runs the algorithm + finalize (test sealed)."""
    from cap_evolve import cli

    project, spec_path = _build_project(tmp_path, "deterministic")
    rc = cli.main(["run", "--spec", str(spec_path), "--project", str(project),
                   "--dashboard", "off", "--run-ts", "det"])
    assert rc == 0

    run_dir = tmp_path / ".capevolve" / "run_det"
    splits = json.loads((run_dir / "splits.json").read_text(encoding="utf-8"))
    assert splits["test_used"] is True, "deterministic mode must finalize + seal the test"
