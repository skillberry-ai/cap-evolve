"""cli.py's optimizer_cmd construction resolves the "propose" role (#665 ws5) via
cap_evolve.model_routing.resolve_model instead of reading `optimizer_model` directly.

Regression coverage: a spec with no `model_routing` block (every existing config)
must produce the byte-identical `--model` flag it produced before this feature
existed — no behavior change for existing configs.
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


def _build_project(tmp_path: Path, extra_yaml: str = "") -> tuple[Path, Path]:
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")

    spec_text = TEMPLATE_SPEC.read_text(encoding="utf-8")
    old_line = 'optimizer_model: ""'
    assert old_line in spec_text
    spec_text = spec_text.replace(old_line, 'optimizer_model: "claude-opus-4"')
    if extra_yaml:
        spec_text += "\n" + extra_yaml + "\n"
    spec_path = project / "capevolve.yaml"
    spec_path.write_text(spec_text, encoding="utf-8")
    return project, spec_path


def _plan(tmp_path: Path, capsys, extra_yaml: str = "") -> dict:
    from cap_evolve import cli

    project, spec_path = _build_project(tmp_path, extra_yaml)
    rc = cli.main(["run", "--spec", str(spec_path), "--project", str(project),
                   "--dashboard", "off", "--plan-only"])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def test_no_model_routing_block_keeps_old_optimizer_model_flag(tmp_path, capsys):
    """Backward compat: identical --model flag to before model_routing existed."""
    plan = _plan(tmp_path, capsys)
    assert "--model claude-opus-4" in plan["optimizer_cmd"], plan["optimizer_cmd"]


def test_model_routing_propose_override_wins(tmp_path, capsys):
    plan = _plan(tmp_path, capsys, "model_routing:\n  propose: claude-sonnet-5")
    assert "--model claude-sonnet-5" in plan["optimizer_cmd"], plan["optimizer_cmd"]
    assert "claude-opus-4" not in plan["optimizer_cmd"]


def test_model_routing_other_role_does_not_affect_propose(tmp_path, capsys):
    """A role this call site doesn't use must not change the --model flag it does use."""
    plan = _plan(tmp_path, capsys, "model_routing:\n  root_cause: claude-sonnet-5")
    assert "--model claude-opus-4" in plan["optimizer_cmd"], plan["optimizer_cmd"]
