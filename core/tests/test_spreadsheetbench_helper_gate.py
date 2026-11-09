"""The common pre-rollout helper gate (exp895): lint + smoke run in the adapter, before any LLM call.

Hill-climb never calls cap-evolve's helper lint or smoke test (only agent-optimize's pregate does), so a
candidate whose helper scripts hold a task id, or do not even import, would otherwise be rolled out. The
gate lives in the shared rollout layer so every arm of the experiment gets the identical check. A failing
candidate scores 0 on every rollout without an LLM call (error_kind=candidate); its evaluation is still
debited by the harness.
"""

import importlib.util
import sys
import textwrap
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "benchmarks" / "spreadsheetbench" / "template"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, REPO / "benchmarks" / "_shared"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_helper_gate", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gate(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    ids = tmp_path / "ids.txt"
    ids.write_text("10452\n105-24\n")
    spec = tmp_path / "capevolve.yaml"
    spec.write_text(textwrap.dedent(f"""\
        surface:
          executable_dirs: ["skills/*/scripts"]
        helpers:
          enabled: true
          lint: true
          smoke: true
          suffixes: [".py"]
          smoke_timeout: 20
          ids_file: {ids}
        """))
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(spec))
    mod._HELPER_GATE_CACHE.clear()
    return mod


def _cand(tmp_path, name, script):
    cand = tmp_path / name
    scripts = cand / "skills" / "spreadsheet-helpers" / "scripts"
    scripts.mkdir(parents=True)
    (cand / "skills" / "spreadsheet-helpers" / "SKILL.md").write_text(
        "---\nname: spreadsheet-helpers\ndescription: test helpers\n---\n# helpers\n")
    if script is not None:
        (scripts / "h.py").write_text(textwrap.dedent(script))
    return cand


def test_gate_is_off_without_the_spec_env(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    monkeypatch.delenv("CAPEVOLVE_HELPERS_SPEC", raising=False)
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    cand = _cand(tmp_path, "c", "import nonexistent_module_xyz\n")
    assert mod._helper_gate_error(cand) is None


def test_clean_helper_passes(gate, tmp_path):
    cand = _cand(tmp_path, "clean", """\
        def normalize_number(s):
            return float(str(s).replace(",", "").strip())
        """)
    assert gate._helper_gate_error(cand) is None


def test_no_scripts_passes(gate, tmp_path):
    assert gate._helper_gate_error(_cand(tmp_path, "empty", None)) is None


def test_task_id_literal_is_refused(gate, tmp_path):
    cand = _cand(tmp_path, "leaky", """\
        def answer(task_id):
            if task_id == "10452":
                return 42
            return None
        """)
    err = gate._helper_gate_error(cand)
    assert err and err.startswith("CANDIDATE_HELPER_GATE") and "lint" in err


def test_import_crash_is_refused_by_the_smoke(gate, tmp_path):
    cand = _cand(tmp_path, "crashy", "import nonexistent_module_xyz\n")
    err = gate._helper_gate_error(cand)
    assert err and "smoke" in err


def test_verdict_is_cached_per_tree(gate, tmp_path, monkeypatch):
    cand = _cand(tmp_path, "cached", "def f(x):\n    return x\n")
    calls = []
    real = gate._helpers.lint_candidate
    monkeypatch.setattr(gate._helpers, "lint_candidate", lambda *a, **k: calls.append(1) or real(*a, **k))
    for _ in range(3):
        assert gate._helper_gate_error(cand) is None
    assert len(calls) == 1, "the lint must run once per distinct tree, not once per rollout"


def test_run_target_returns_a_candidate_fault_without_an_llm_call(gate, tmp_path, monkeypatch):
    cand = _cand(tmp_path, "leaky2", 'ID = "105-24"\n')
    (cand / "prompt.md").write_text("system")
    monkeypatch.setattr(gate, "_task_template_error", lambda ctx: None)
    # a fake litellm (CI does not install it): any completion call fails the test
    fake = types.ModuleType("litellm")
    fake.completion = lambda *a, **k: pytest.fail("no LLM call may be made")
    monkeypatch.setitem(sys.modules, "litellm", fake)
    task = gate.Task(id="10452", input={"instruction": "", "spreadsheet_path": "", "instruction_type": "",
                                        "answer_position": "A1"})
    r = gate.Adapter().run_target(task, cand, seed=0)
    assert r.error and r.error.startswith("CANDIDATE_HELPER_GATE")
    assert r.metadata["error_kind"] == "candidate" and r.metadata["helper_gate"] == "failed"


# ---- review of #954: the spec alone enables the gate; a broken config is loud; the seed is the parent ----

_LEAKY = 'ID = "105-24"\n'


def _write_spec(tmp_path, *, enabled=True, capability_path=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ids = tmp_path / "ids.txt"
    ids.write_text("10452\n105-24\n")
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    cap = f"capability_path: {capability_path}\n" if capability_path else ""
    spec = proj / "capevolve.yaml"
    spec.write_text(cap + textwrap.dedent(f"""\
        surface:
          executable_dirs: ["skills/*/scripts"]
        helpers:
          enabled: {str(enabled).lower()}
          lint: true
          smoke: false
          suffixes: [".py"]
          ids_file: {ids}
        """))
    return spec


def test_the_spec_alone_turns_the_gate_on(tmp_path, monkeypatch):
    # helpers.enabled in the spec is enough: CAPEVOLVE_HELPERS is not also needed
    mod = _load_adapter_module()
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path, enabled=True)))
    mod._HELPER_GATE_CACHE.clear()
    err = mod._helper_gate_error(_cand(tmp_path, "leaky", _LEAKY))
    assert err and err.startswith("CANDIDATE_HELPER_GATE")


def test_a_spec_with_helpers_disabled_keeps_the_gate_off(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path, enabled=False)))
    mod._HELPER_GATE_CACHE.clear()
    assert mod._helper_gate_error(_cand(tmp_path, "leaky", _LEAKY)) is None


def test_the_env_switch_still_overrides_the_spec(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "0")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path, enabled=True)))
    mod._HELPER_GATE_CACHE.clear()
    assert mod._helper_gate_error(_cand(tmp_path, "leaky", _LEAKY)) is None


def test_a_missing_spec_file_raises_the_config_error(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(tmp_path / "nope.yaml"))
    mod._HELPER_GATE_CACHE.clear()
    with pytest.raises(mod.HelperGateConfigError):
        mod._helper_gate_error(_cand(tmp_path, "c", "x = 1\n"))


def test_creating_the_adapter_with_a_broken_spec_raises(tmp_path, monkeypatch):
    # the check that stops every caller (harness, cap-evolve check, or any other rollout layer) before a rollout
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(tmp_path / "nope.yaml"))
    with pytest.raises(mod.HelperGateConfigError):
        mod.Adapter()


def test_an_invalid_helpers_table_raises_at_creation_too(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("helpers:\n  enabled: true\n  no_such_key: 1\n")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(spec))
    with pytest.raises(mod.HelperGateConfigError, match="no_such_key"):
        mod.Adapter()


def test_live_raises_the_config_error_when_the_spec_breaks_later(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    spec = _write_spec(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(spec))
    adapter = mod.Adapter()
    spec.unlink()
    cand = _cand(tmp_path, "c", "x = 1\n")
    monkeypatch.setattr(mod, "_task_template_error", lambda ctx: None)
    with pytest.raises(mod.HelperGateConfigError):
        with adapter.live(cand):
            pass


def test_run_target_reports_a_broken_config_as_infra_not_as_a_candidate_fault(tmp_path, monkeypatch):
    # the spec breaks after the adapter was created: never scored 0, no error_kind=candidate
    mod = _load_adapter_module()
    spec = _write_spec(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(spec))
    adapter = mod.Adapter()
    spec.unlink()
    mod._HELPER_GATE_CACHE.clear()
    cand = _cand(tmp_path, "c", "x = 1\n")
    (cand / "prompt.md").write_text("system")
    monkeypatch.setattr(mod, "_task_template_error", lambda ctx: None)
    fake = types.ModuleType("litellm")
    fake.completion = lambda *a, **k: pytest.fail("no LLM call may be made")
    monkeypatch.setitem(sys.modules, "litellm", fake)
    task = mod.Task(id="10452", input={"instruction": "", "spreadsheet_path": "", "instruction_type": "",
                                       "answer_position": "A1"})
    r = adapter.run_target(task, cand, seed=0)
    assert r.error and r.error.startswith("HELPER_GATE_CONFIG_ERROR")
    assert r.metadata.get("error_kind") != "candidate" and r.metadata["helper_gate"] == "config_error"


def test_a_helper_the_seed_already_ships_is_not_blamed_on_the_candidate(tmp_path, monkeypatch):
    # the seed ships a helper that fails the lint; a candidate that leaves it byte-identical is not refused,
    # while one that changes it into a (still failing) different file is
    mod = _load_adapter_module()
    seed = tmp_path / "seed_capability"
    sh = seed / "skills" / "spreadsheet-helpers" / "scripts"
    sh.mkdir(parents=True)
    (sh / "h.py").write_text(_LEAKY)
    spec = _write_spec(tmp_path, capability_path="../seed_capability")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(spec))
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    mod._HELPER_GATE_CACHE.clear()
    same = _cand(tmp_path, "same", _LEAKY)
    assert mod._helper_gate_error(same) is None
    changed = _cand(tmp_path, "changed", 'ID = "10452"\n')
    err = mod._helper_gate_error(changed)
    assert err and err.startswith("CANDIDATE_HELPER_GATE")


def test_the_seed_dir_is_found_relative_to_the_project_folder(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    (tmp_path / "proj" / "seed_x").mkdir(parents=True)
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path, capability_path="seed_x")))
    cfg, seed = mod._helper_gate_config()
    assert seed == (tmp_path / "proj" / "seed_x") and cfg["lint"]


def test_the_verdict_cache_is_keyed_by_the_seed_too(tmp_path, monkeypatch):
    # the same candidate tree is refused against no seed and accepted against a seed that ships the same file;
    # one process, cache kept, so a key without the seed would reuse the first verdict
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    cand = _cand(tmp_path, "c", _LEAKY)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path / "a")))
    mod._HELPER_GATE_CACHE.clear()
    assert mod._helper_gate_error(cand)
    seed = tmp_path / "b" / "seed_capability" / "skills" / "spreadsheet-helpers" / "scripts"
    seed.mkdir(parents=True)
    (seed / "h.py").write_text(_LEAKY)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path / "b", capability_path="../seed_capability")))
    assert mod._helper_gate_error(cand) is None


def test_the_cache_key_covers_nested_helper_files(tmp_path, monkeypatch):
    # lint and smoke scan executable_dirs recursively; two trees that differ only in a nested helper must not share
    # a verdict
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path)))
    mod._HELPER_GATE_CACHE.clear()
    clean = _cand(tmp_path, "clean", "x = 1\n")
    nested = _cand(tmp_path, "nested", "x = 1\n")
    sub = nested / "skills" / "spreadsheet-helpers" / "scripts" / "lib"
    sub.mkdir()
    (sub / "inner.py").write_text(_LEAKY)
    assert mod._helper_gate_error(clean) is None
    assert mod._helper_gate_error(nested), "a leaky nested helper must not reuse the clean tree's verdict"


def test_the_spec_is_parsed_once_not_per_rollout(tmp_path, monkeypatch):
    mod = _load_adapter_module()
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_write_spec(tmp_path)))
    mod._HELPER_GATE_CONFIGS.clear()
    reads = []
    import cap_evolve.specfile as sf
    real = sf.read_yaml
    monkeypatch.setattr(sf, "read_yaml", lambda *a, **k: reads.append(1) or real(*a, **k))
    cand = _cand(tmp_path, "c", "x = 1\n")
    for _ in range(5):
        mod._helper_gate_error(cand)
    assert len(reads) == 1
