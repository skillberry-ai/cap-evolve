"""specfile.read_yaml's tolerant fallback (no PyYAML): #676 added block-sequence-of-
mappings support (`key:\n  - a: 1\n    b: 2`) and flow-mapping support (`key: {a: 1}`),
needed to parse `objectives:` — a key no real capevolve.yaml used before #665/#667's
pareto gate shipped. Covers both forms the real template/project files use, plus a
regression check that the existing scalar/flow-list/one-level-nesting behavior these
tests already exercised elsewhere is unaffected.
"""
import tempfile
from pathlib import Path

from cap_evolve.specfile import read_yaml, resolve_spec_path, spec_for_run


def test_block_sequence_of_multiline_mappings():
    """The real run_v2_multiobjective project yaml's `objectives:` shape."""
    y = (
        "gate_mode: pareto\n"
        "objectives:\n"
        "  - name: reward\n"
        "    direction: maximize\n"
        "  - name: cost\n"
        "    direction: minimize\n"
        "max_iterations: 12\n"
    )
    assert read_yaml(y) == {
        "gate_mode": "pareto",
        "objectives": [
            {"name": "reward", "direction": "maximize"},
            {"name": "cost", "direction": "minimize"},
        ],
        "max_iterations": 12,
    }


def test_block_sequence_of_flow_mappings():
    """The benchmarks/_scaffold/project/capevolve.yaml documented example's `objectives:` shape."""
    y = (
        "objectives:\n"
        "  - {name: reward, direction: maximize}\n"
        "  - {name: cost, direction: minimize}\n"
    )
    assert read_yaml(y)["objectives"] == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]


def test_flow_mapping_scalar_value():
    assert read_yaml("x: {a: 1, b: two}\n")["x"] == {"a": 1, "b": "two"}


def test_existing_scalar_list_and_one_level_nesting_still_work():
    """Regression check: #676 only ADDS sequence support, scalars/flow-lists/single-
    level map nesting (the forms every other test's spec fixtures already rely on)
    must read exactly as before."""
    y = (
        "gate_mode: paired\n"
        "capabilities: [system-prompt, tools]\n"
        "metrics_display: []\n"
        "intervention:\n"
        "  type: direct\n"
    )
    assert read_yaml(y) == {
        "gate_mode": "paired",
        "capabilities": ["system-prompt", "tools"],
        "metrics_display": [],
        "intervention": {"type": "direct"},
    }


def test_resolve_spec_path_prefers_the_run_s_own_recorded_spec():
    """A non-default spec filename (`cap-evolve run --spec capevolve.v2.yaml`) must
    resolve to ITSELF, not silently fall back to project/capevolve.yaml — this is the
    bug behind #676's Config tab showing the wrong (generic) spec for a real
    multi-objective run."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        project = base / "project"
        project.mkdir()
        (project / "capevolve.yaml").write_text("gate_mode: paired\n", encoding="utf-8")
        variant = project / "capevolve.v2.yaml"
        variant.write_text("gate_mode: pareto\nobjectives:\n  - name: reward\n    direction: maximize\n",
                            encoding="utf-8")

        class _RD:
            events_path = base / "events.jsonl"

        _RD.events_path.write_text("", encoding="utf-8")
        assert resolve_spec_path(_RD, project) == project / "capevolve.yaml"
        assert spec_for_run(_RD, project)["gate_mode"] == "paired"

        _RD.events_path.write_text(
            '{"kind": "run_config", "spec": "%s"}\n' % variant, encoding="utf-8")
        assert resolve_spec_path(_RD, project) == variant
        assert spec_for_run(_RD, project)["gate_mode"] == "pareto"


# ---- invalid YAML must be reported, never silently misread ---------------------

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

from cap_evolve.specfile import SpecError

_BROKEN = 'algorithm_skill: hill-climb\nmax_usd: "5\nsplits: [a, b\n'


def test_malformed_yaml_raises_with_line_number():
    with pytest.raises(SpecError) as ei:
        read_yaml("a: 1\nsplits: [a, b\n", source="capevolve.yaml", strict=True)
    e = ei.value
    assert e.line == 3
    assert "capevolve.yaml" in str(e) and "line 3" in str(e)


def test_unclosed_quote_names_the_line_it_was_opened_on():
    with pytest.raises(SpecError) as ei:
        read_yaml(_BROKEN, source="capevolve.yaml", strict=True)
    assert ei.value.line is not None
    assert "opened at line 2" in str(ei.value)


def test_tab_indent_raises():
    with pytest.raises(SpecError) as ei:
        read_yaml("a: 1\n\tb: 2\n", strict=True)
    assert ei.value.line == 2
    assert "invalid YAML at line 2" in str(ei.value) and "YAML in YAML" not in str(ei.value)


_META_UNQUOTED_COLON = (
    "name: gepa\n"
    "kind: algorithm\n"
    "summary: Reflective evolution: mutate the prompt from failures\n"
)


def test_lenient_default_loads_skill_meta_with_unquoted_colon():
    # Skill meta.yaml / SKILL.md frontmatter is not always strict YAML; the default
    # (strict=False) must fall back to the minimal reader instead of raising.
    data = read_yaml(_META_UNQUOTED_COLON, source="meta.yaml")
    assert data["name"] == "gepa" and data["kind"] == "algorithm"
    assert data["summary"].startswith("Reflective evolution")
    with pytest.raises(SpecError):
        read_yaml(_META_UNQUOTED_COLON, source="meta.yaml", strict=True)


def test_valid_yaml_still_parses():
    assert read_yaml('max_usd: 5\nsplits: [a, b]\nname: "x"\n') == {
        "max_usd": 5, "splits": ["a", "b"], "name": "x"}


def test_fallback_reader_used_only_without_pyyaml(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)  # `import yaml` -> ImportError
    assert read_yaml("max_usd: 5\nsplits: [a, b]\nnested:\n  k: v\n") == {
        "max_usd": 5, "splits": ["a", "b"], "nested": {"k": "v"}}


def _broken_project(tmp_path):
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    (proj / "capevolve.yaml").write_text(_BROKEN, encoding="utf-8")
    return proj


def test_doctor_fails_the_spec_row_on_broken_yaml(tmp_path):
    from cap_evolve.cli import _doctor_checks
    rows = {r["name"]: r for r in _doctor_checks(_broken_project(tmp_path))}
    assert rows["spec"]["status"] == "fail"
    assert "invalid YAML" in rows["spec"]["detail"] and "line" in rows["spec"]["detail"]


def test_check_reports_broken_yaml_as_a_problem(tmp_path):
    from cap_evolve import check
    rep = check.run_check(_broken_project(tmp_path))
    assert not rep.ok
    assert any("invalid YAML" in p for p in rep.problems)


def test_run_refuses_a_broken_spec_without_a_traceback(tmp_path):
    from cap_evolve import cli
    proj = _broken_project(tmp_path)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(["run", "--project", str(proj)])
    assert rc == 1
    payload = json.loads(out.getvalue().strip().splitlines()[-1])
    assert payload["step"] == "spec" and "invalid YAML" in payload["error"]
    assert "Traceback" not in err.getvalue()


# --- a spec that is valid YAML but not a mapping (T-6) -----------------------------

_NOT_A_MAPPING = {"list": "- max_usd: 5\n", "string": "just a string\n"}


def _project_with(tmp_path, text):
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    (proj / "capevolve.yaml").write_text(text, encoding="utf-8")
    return proj


@pytest.mark.parametrize("kind", sorted(_NOT_A_MAPPING))
def test_strict_read_rejects_a_non_mapping_spec(kind):
    with pytest.raises(SpecError) as ei:
        read_yaml(_NOT_A_MAPPING[kind], source="capevolve.yaml", strict=True)
    assert "must be a mapping of keys and values" in str(ei.value)
    # lenient (skill metadata) reading and an empty spec are unchanged
    read_yaml(_NOT_A_MAPPING[kind])
    assert read_yaml("", strict=True) == {}


@pytest.mark.parametrize("kind", sorted(_NOT_A_MAPPING))
def test_doctor_fails_the_spec_row_on_a_non_mapping_spec(tmp_path, kind):
    from cap_evolve.cli import _doctor_checks
    rows = {r["name"]: r for r in _doctor_checks(_project_with(tmp_path, _NOT_A_MAPPING[kind]))}
    assert rows["spec"]["status"] == "fail"
    assert "must be a mapping of keys and values" in rows["spec"]["detail"]
    assert "fix the YAML" in rows["spec"]["fix"]


@pytest.mark.parametrize("kind", sorted(_NOT_A_MAPPING))
def test_check_reports_a_non_mapping_spec(tmp_path, kind):
    from cap_evolve import check
    rep = check.run_check(_project_with(tmp_path, _NOT_A_MAPPING[kind]))
    assert not rep.ok
    assert any("must be a mapping of keys and values" in p for p in rep.problems)


@pytest.mark.parametrize("cmd", [["run", "--dry-run"], ["estimate"]])
@pytest.mark.parametrize("kind", sorted(_NOT_A_MAPPING))
def test_run_and_estimate_refuse_a_non_mapping_spec(tmp_path, kind, cmd):
    from cap_evolve import cli
    proj = _project_with(tmp_path, _NOT_A_MAPPING[kind])
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main([*cmd, "--project", str(proj)])
    assert rc == 1
    payload = json.loads(out.getvalue().strip().splitlines()[-1])
    assert payload["step"] == "spec"
    assert "must be a mapping of keys and values" in payload["error"]
    assert "Traceback" not in err.getvalue()
