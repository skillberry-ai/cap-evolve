"""cli.py's `optimizer_usd_per_iter` -> `--usd-budget` check is a Python truthiness test on a
YAML-parsed value. Every committed example quotes it as a bare number (0.0, 40.0), which YAML
parses as int/float and `bool(0.0)` is correctly False. But a capevolve.yaml that quotes it as
the STRING "0" (legal YAML for a value the reader does not schema-check) hits the identical
footgun #530 fixed one layer up, in benchmarks.yml's `||` chain: `bool("0")` is True in Python,
so a plain `if spec.get(...)` would render `--usd-budget 0.0` — an unintended near-zero cap —
instead of treating it as off. Flagged in review of #530; see cli.py's `_cmd_run`.
"""

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


def _build_project(tmp_path: Path, optimizer_usd_per_iter_literal: str) -> tuple[Path, Path]:
    """Build a runnable toy_calc project with `optimizer_usd_per_iter` set to the given raw
    YAML literal (e.g. '"0"', '0.0', '4.0')."""
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")

    spec_text = TEMPLATE_SPEC.read_text(encoding="utf-8")
    old_line = "optimizer_usd_per_iter: 0.0"
    assert old_line in spec_text
    spec_text = spec_text.replace(
        old_line, f"optimizer_usd_per_iter: {optimizer_usd_per_iter_literal}"
    )
    spec_path = project / "capevolve.yaml"
    spec_path.write_text(spec_text, encoding="utf-8")
    return project, spec_path


def _plan(tmp_path: Path, capsys, optimizer_usd_per_iter_literal: str) -> dict:
    import json

    from cap_evolve import cli

    project, spec_path = _build_project(tmp_path, optimizer_usd_per_iter_literal)
    rc = cli.main(["run", "--spec", str(spec_path), "--project", str(project),
                   "--dashboard", "off", "--plan-only"])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def test_a_quoted_string_zero_is_still_treated_as_off(tmp_path, capsys):
    """The exact footgun: "0" is truthy in Python, but must mean the same as 0.0 here."""
    plan = _plan(tmp_path, capsys, '"0"')
    assert "--usd-budget" not in plan["optimizer_cmd"], plan["optimizer_cmd"]


def test_a_bare_numeric_zero_is_off(tmp_path, capsys):
    plan = _plan(tmp_path, capsys, "0.0")
    assert "--usd-budget" not in plan["optimizer_cmd"], plan["optimizer_cmd"]


def test_an_empty_string_is_off(tmp_path, capsys):
    plan = _plan(tmp_path, capsys, '""')
    assert "--usd-budget" not in plan["optimizer_cmd"], plan["optimizer_cmd"]


def test_a_real_ceiling_still_renders_the_flag(tmp_path, capsys):
    plan = _plan(tmp_path, capsys, "4.0")
    assert "--usd-budget 4.0" in plan["optimizer_cmd"], plan["optimizer_cmd"]


def test_a_quoted_real_ceiling_still_renders_the_flag(tmp_path, capsys):
    """Only "0"/""/0/None are the off-values; any other quoted string still parses through
    float() the same as its unquoted form."""
    plan = _plan(tmp_path, capsys, '"4.0"')
    assert "--usd-budget 4.0" in plan["optimizer_cmd"], plan["optimizer_cmd"]
