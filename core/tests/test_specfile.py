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


# --- strict reading WITHOUT PyYAML (core has no runtime deps; CI installs none) -------

_STRICT_CASES = {
    "unclosed-quote": ('algorithm_skill: hill-climb\nmax_usd: "5\nsplits: [a, b\n', "opened at line 2"),
    "unclosed-bracket": ("a: 1\nsplits: [a, b\n", "opened at line 2"),
    "tab-indent": ("a: 1\n\tb: 2\n", "line 2"),
    "list-top-level": ("- max_usd: 5\n", "must be a mapping of keys and values"),
    "string-top-level": ("just a string\n", "must be a mapping of keys and values"),
    "unquoted-colon": ("name: gepa\nsummary: Reflective evolution: mutate it\n", "line 2"),
    "bad-date": ("max_usd: 5\ncreated: 2024-13-01\n", "line 2"),
    "bad-tag": ("max_usd: 5\na: !!int x\n", "line 2"),
    "wrong-closer": ("splits: [a, b}\n", "line 1"),
    "text-after-quote": ('run_name: "a" b\n', "line 1"),
    "indented-under-a-value": ("max_usd: 5\n  stall: 2\n", "line 2"),
    # round 4 (T-34): bad dedents must not move a key into the wrong block
    "bad-dedent-map": ("helpers:\n    enabled: true\n  max_usd: 5\n", "line 3"),
    "bad-dedent-list": ("a:\n  - x\n - y\n", "line 3"),
    "bad-dedent-in-item": ("a:\n  - b: 1\n   c: 2\n", "line 3"),
    "indented-first-line": ("  a: 1\nb: 2\n", "line"),
    "second-document": ("max_usd: 5\n---\nmax_usd: 50\n", "line 2"),
    "bad-escape": ('k: "C:\\Users\\x"\n', "line 1"),
    "dash-after-key": ("k: - 5\n", "line 1"),
    "bare-dash-after-key": ("k: -\n", "line 1"),
    "percent-value": ("k: %x\n", "line 1"),
    "closer-value": ("k: ]x\n", "line 1"),
    "colon-in-flow-value": ("k: {a: b: c}\n", "line 1"),
    "empty-flow-item": ("k: [a, , b]\n", "line 1"),
}


@pytest.fixture(params=["with-pyyaml", "without-pyyaml"])
def yaml_env(request, monkeypatch):
    """Run a test with PyYAML (when installed) and with ``import yaml`` hidden."""
    if request.param == "with-pyyaml":
        pytest.importorskip("yaml")
    else:
        monkeypatch.setitem(sys.modules, "yaml", None)
    return request.param


@pytest.mark.parametrize("case", sorted(_STRICT_CASES))
def test_strict_read_refuses_broken_specs_with_and_without_pyyaml(yaml_env, case):
    text, needle = _STRICT_CASES[case]
    with pytest.raises(SpecError) as ei:
        read_yaml(text, source="capevolve.yaml", strict=True)
    assert "capevolve.yaml" in str(ei.value) and needle in str(ei.value)
    # lenient reading (skill meta.yaml / frontmatter) never fails, on any of them
    read_yaml(text)


def test_strict_read_without_pyyaml_uses_the_built_in_reader(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)  # `import yaml` -> ImportError
    with pytest.raises(SpecError) as ei:
        read_yaml('max_usd: "5\nnum_trials: 1\n', source="capevolve.yaml", strict=True)
    assert ei.value.line == 3 and "opened at line 1" in str(ei.value)
    good = ("max_usd: 5  # cap\nsplits: [a, 'b, c']\nrun_name: \"x # y\"\nnote: don't # z\n"
            "objectives:\n  - name: reward\n    direction: maximize\nseed: ~\n")
    assert read_yaml(good, strict=True) == {
        "max_usd": 5, "splits": ["a", "b, c"], "run_name": "x # y", "note": "don't",
        "objectives": [{"name": "reward", "direction": "maximize"}], "seed": None}


@pytest.mark.parametrize("text", ["notes: |\n  hi\n", "splits: [a,\n  b]\n", '{"max_usd": 5}\n',
                                  "[1, 2]\n",
                                  # round 4 (T-34): valid YAML the built-in reader would misread
                                  "k: [a: 1]\n", 'k: ["a": 1]\n', "split_ids:\n- - t1\n  - t2\n",
                                  "l:\n  - -\n", 'k: "\\x41"\n', 'k: "\\e"\n', 'k: "\\0"\n',
                                  'k: {a: "\\e"}\n'])
def test_strict_built_in_reader_refuses_valid_yaml_it_cannot_read(monkeypatch, text):
    # valid YAML, but the built-in reader would misread it: refuse with a clear message
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(SpecError) as ei:
        read_yaml(text, source="capevolve.yaml", strict=True)
    assert "line" in str(ei.value)


def test_every_shipped_spec_reads_the_same_with_and_without_pyyaml(monkeypatch):
    yaml = pytest.importorskip("yaml")
    import re
    import subprocess
    repo = Path(__file__).resolve().parents[2]
    files = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout.split()
    specs = [f for f in files if re.search(r"(^|/)capevolve[^/]*\.ya?ml$", f)]
    assert specs
    texts, want = {}, {}
    for f in specs:
        # appworld templates hold `@NAME@` placeholders a setup script fills in
        texts[f] = re.sub(r"@[A-Z_]+@", "placeholder", (repo / f).read_text(encoding="utf-8"))
        want[f] = yaml.safe_load(texts[f])
    monkeypatch.setitem(sys.modules, "yaml", None)  # now the built-in reader
    for f in specs:
        assert read_yaml(texts[f], source=f, strict=True) == want[f], f


# --- PyYAML errors that are not yaml.YAMLError (bad values built after parsing) -------

_BAD_VALUES = ["created: 2024-13-01\n", "a: !!int x\n", "a: !!timestamp x\n"]


@pytest.mark.parametrize("text", _BAD_VALUES)
def test_bad_values_are_a_spec_error_in_strict_and_a_dict_in_lenient(yaml_env, text):
    with pytest.raises(SpecError) as ei:
        read_yaml("max_usd: 5\n" + text, source="capevolve.yaml", strict=True)
    assert ei.value.line == 2 and "capevolve.yaml, line 2" in str(ei.value)
    assert isinstance(read_yaml("max_usd: 5\n" + text), dict)


@pytest.mark.parametrize("cmd", [["run", "--dry-run"], ["estimate"]])
@pytest.mark.parametrize("text", _BAD_VALUES)
def test_run_and_estimate_refuse_a_bad_value_without_a_traceback(tmp_path, yaml_env, cmd, text):
    from cap_evolve import cli
    proj = _project_with(tmp_path, "max_usd: 5\n" + text)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main([*cmd, "--project", str(proj)])
    assert rc == 1
    payload = json.loads(out.getvalue().strip().splitlines()[-1])
    assert payload["step"] == "spec" and payload["line"] == 2
    assert "Traceback" not in err.getvalue()


# --- split_seed may be negative; other numbers may not --------------------------------

def test_a_negative_split_seed_is_allowed():
    from cap_evolve.specfile import numeric_spec_errors
    assert numeric_spec_errors({"split_seed": -1}) == []
    assert numeric_spec_errors({"split_seed": 0}) == []
    assert [e["key"] for e in numeric_spec_errors({"split_seed": 1.5})] == ["split_seed"]
    assert "0 or more" not in numeric_spec_errors({"split_seed": "x"})[0]["error"]
    assert [e["key"] for e in numeric_spec_errors({"max_usd": -1})] == ["max_usd"]
    assert [e["key"] for e in numeric_spec_errors({"max_usd": "5"})] == ["max_usd"]


# --- a spec broken DURING a run keeps its in-run settings (spec_for_run) --------------

def test_mid_run_syntax_error_keeps_pooled_and_warns_once(tmp_path, yaml_env, capsys):
    from cap_evolve import RunDir
    from cap_evolve.gatecfg import GateConfig
    proj = tmp_path / "project"
    proj.mkdir()
    spec = proj / "capevolve.yaml"
    spec.write_text("split_mode: pooled\nbudget_reserve: true\n", encoding="utf-8")
    rd = RunDir.create(tmp_path / ".capevolve", ts="midrun")
    rd.log_event("spec_resolved", spec=str(spec))
    assert GateConfig.for_run(rd).split_mode == "pooled"
    # someone edits the spec while the run goes on, and leaves an unclosed quote
    spec.write_text('split_mode: pooled\nbudget_reserve: true\nrun_name: "oops\n', encoding="utf-8")
    for _ in range(3):
        cfg = GateConfig.for_run(rd)
        assert cfg.split_mode == "pooled" and cfg.budget_reserve is True
    err = capsys.readouterr().err
    assert err.count("cannot be read strictly") == 1 and str(spec) in err
    events = [json.loads(ln) for ln in rd.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    unreadable = [e for e in events if e.get("kind") == "spec_unreadable"]
    assert len(unreadable) == 1 and unreadable[0]["spec"] == str(spec) and "line" in unreadable[0]["error"]


def test_spec_unreadable_is_written_once_per_run_across_processes(tmp_path, yaml_env, capsys):
    # agent-optimize runs each step (spend.py, measure.py, ...) as its own process: a
    # fresh process (empty in-process set) must find the earlier event and stay quiet.
    from cap_evolve import RunDir, specfile
    proj = tmp_path / "project"
    proj.mkdir()
    spec = proj / "capevolve.yaml"
    spec.write_text("split_mode: pooled\n", encoding="utf-8")
    rd = RunDir.create(tmp_path / ".capevolve", ts="procs")
    rd.log_event("spec_resolved", spec=str(spec))
    spec.write_text('split_mode: pooled\nrun_name: "oops\n', encoding="utf-8")
    with rd.events_path.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")  # a bad line in the log must not crash the check

    def unreadable():
        evs = []
        for ln in rd.events_path.read_text(encoding="utf-8").splitlines():
            try:
                evs.append(json.loads(ln))
            except ValueError:
                pass
        return [e for e in evs if e.get("kind") == "spec_unreadable"]

    for _ in range(5):
        specfile._SPEC_WARNED.clear()  # a new process
        assert specfile.spec_for_run(rd).get("split_mode") == "pooled"
    assert len(unreadable()) == 1
    assert capsys.readouterr().err.count("cannot be read strictly") == 1
    # a different error on the same spec is a new event
    spec.write_text("split_mode: pooled\nrun_name: [oops\n", encoding="utf-8")
    for _ in range(3):
        specfile._SPEC_WARNED.clear()
        specfile.spec_for_run(rd)
    got = unreadable()
    assert len(got) == 2 and got[0]["error"] != got[1]["error"]



# --- the built-in strict reader reads valid YAML the same as PyYAML (round 2) ---------
# Each case: (text, the value PyYAML gives). The built-in reader is checked against that
# value in every environment; when PyYAML is installed, the value itself is checked too.

_SAME_AS_PYYAML = {
    "bom": ("\ufeffmax_usd: 5\nmax_iterations: 3\n", {"max_usd": 5, "max_iterations": 3}),
    "quoted-keys": ('"max_usd": 5\n\'stall\': 2\n"a:b": 1\n', {"max_usd": 5, "stall": 2, "a:b": 1}),
    "yaml11-bools": ("budget_reserve: no\ndashboard: off\na: yes\nb: On\nc: NO\nd: yEs\n"
                     "helpers:\n  enabled: no\n",
                     {"budget_reserve": False, "dashboard": False, "a": True, "b": True, "c": False,
                      "d": "yEs", "helpers": {"enabled": False}}),
    "empty-values": ("a: 1\nmax_usd:\nrun_name:\nb: 2\nobservers:\n",
                     {"a": 1, "max_usd": None, "run_name": None, "b": 2, "observers": None}),
    "bare-dash-items": ("x:\n  -\n    k: v\n    j: 2\n  -\n  - 3\n",
                        {"x": [{"k": "v", "j": 2}, None, 3]}),
    "dash-key-with-no-value": ("o:\n  - name:\n    b: 1\n  - name:\n      c: 2\n",
                               {"o": [{"name": None, "b": 1}, {"name": {"c": 2}}]}),
    "numbers": ("a: .5\nb: +5\nc: 1_000\nd: 0x1F\ne: 1.50\nf: 3.\ng: 1.5e+3\nh: 1e3\ni: 007\n"
                "j: 1.2.3\nk: -2\n",
                {"a": 0.5, "b": 5, "c": 1000, "d": 31, "e": 1.5, "f": 3.0, "g": 1500.0, "h": "1e3",
                 "i": 7, "j": "1.2.3", "k": -2}),
    "flush-list-items": ("capabilities:\n- system-prompt\n- tools\nobjectives:\n- name: reward\n"
                         "  direction: maximize\nmax_usd: 5\n",
                         {"capabilities": ["system-prompt", "tools"],
                          "objectives": [{"name": "reward", "direction": "maximize"}], "max_usd": 5}),
    # round 4 (T-34): flow mappings, spaces after a dash, document markers
    "flow-quoted-keys": ('helpers: {"enabled": true}\nk: {\'a\': 1, "b":2}\n',
                         {"helpers": {"enabled": True}, "k": {"a": 1, "b": 2}}),
    "flow-quoted-comma": ('objectives:\n  - {name: reward, description: "accuracy, higher is better"}\n'
                          "l: [a, 'b, c', don't]\n",
                          {"objectives": [{"name": "reward", "description": "accuracy, higher is better"}],
                           "l": ["a", "b, c", "don't"]}),
    "flow-bare-keys": ("k: {a}\nj: {a: }\nm: {a, b: 1}\n",
                       {"k": {"a": None}, "j": {"a": None}, "m": {"a": None, "b": 1}}),
    "flow-nested": ("k: {a: [1, 2], b: {c: d}}\nl: [a,]\n",
                    {"k": {"a": [1, 2], "b": {"c": "d"}}, "l": ["a"]}),
    "spaces-after-dash": ("objectives:\n-   name: reward\n    direction: maximize\n",
                          {"objectives": [{"name": "reward", "direction": "maximize"}]}),
    "document-markers": ("# c\n---\nmax_usd: 5\n...\n", {"max_usd": 5}),
    "json-escapes": ('k: "a\\nb \\u00e9"\n', {"k": "a\nb \u00e9"}),
}


@pytest.mark.parametrize("case", sorted(_SAME_AS_PYYAML))
def test_built_in_strict_reader_reads_valid_yaml_like_pyyaml(case, monkeypatch):
    text, want = _SAME_AS_PYYAML[case]
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:
        assert yaml.safe_load(text.lstrip("\ufeff")) == want  # the expected value is PyYAML's
    monkeypatch.setitem(sys.modules, "yaml", None)
    assert read_yaml(text, source="capevolve.yaml", strict=True) == want


def test_the_built_in_reader_never_raises_a_non_spec_error(monkeypatch):
    # any failure inside the built-in reader is a SpecError with the line in strict mode, and
    # never an exception at all in lenient mode
    from cap_evolve import specfile
    monkeypatch.setitem(sys.modules, "yaml", None)
    monkeypatch.setattr(specfile, "_coerce", lambda v: (_ for _ in ()).throw(TypeError("boom")))
    with pytest.raises(SpecError) as ei:
        read_yaml("a: 1\n", source="capevolve.yaml", strict=True)
    assert ei.value.line == 1 and "TypeError" in str(ei.value)
    assert read_yaml("a: 1\n") == {}


def test_read_spec_file_drops_a_bom(tmp_path, yaml_env):
    from cap_evolve.specfile import read_spec_file
    f = tmp_path / "capevolve.yaml"
    f.write_bytes(b"\xef\xbb\xbfmax_usd: 5\n")
    assert read_spec_file(f) == {"max_usd": 5}


@pytest.mark.parametrize("value, want", [('"no"', False), ('"off"', False), ("no", False),
                                         ('"yes"', True), ("true", True), (None, False)])
def test_budget_reserve_reads_no_and_off_as_off(tmp_path, monkeypatch, value, want):
    from cap_evolve import RunDir, harness
    monkeypatch.delenv(harness.BUDGET_RESERVE_ENV, raising=False)
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("max_usd: 5\n" + (f"budget_reserve: {value}\n" if value else ""), encoding="utf-8")
    rd = RunDir.create(tmp_path / ".capevolve", ts="br")
    rd.log_event("spec_resolved", spec=str(spec))
    assert harness.resolve_budget_reserve(None, rd) is want
