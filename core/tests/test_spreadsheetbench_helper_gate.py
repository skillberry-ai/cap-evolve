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
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
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
