"""The SpreadsheetBench adapter's helper gate, for optimizers that call ``run_target`` directly.

cap-evolve's own loops run the shared helper gate (``cap_evolve.helper_gate``) before any rollout; that is tested in
test_helper_gate.py and test_helper_gate_wiring.py. An external optimizer has no such loop, so the adapter runs the
SAME gate when ``CAPEVOLVE_HELPERS_SPEC`` names a spec. What is proved here:

* it is off unless ``CAPEVOLVE_HELPERS_SPEC`` is set (every run so far), and then nothing changes;
* its verdict is the shared gate's, for a clean, a leaking and a broken helper;
* a config that cannot run stops the caller at ``Adapter()`` / ``live()``, and is an infra error (never a 0) in
  ``run_target``: the agent not loading the helpers the gate checks, no ``CAPEVOLVE_HELPERS_SEED``, an unreadable
  ``ids_file``, an invalid ``helpers:`` table;
* the verdict cache: one check per distinct tree, reset by anything the verdict depends on (any file of the
  tree, the config, the ids_file bytes, the seed), with a lock per tree so other trees are not blocked;
* a helper file that cannot be read is the candidate's own fault, reported as such.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import textwrap
import threading
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "benchmarks" / "spreadsheetbench" / "template"
for _p in (REPO / "core", ADAPTER_DIR, REPO / "benchmarks" / "_shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cap_evolve import helper_gate, helpers  # noqa: E402

LEAK = 'ID = "105-24"\n'
BROKEN = "import nonexistent_module_xyz\n"
CLEAN = "def f(x):\n    return x\n"


def _load():
    spec = importlib.util.spec_from_file_location("_sb_adapter_ext_gate", ADAPTER_DIR / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod(monkeypatch):
    for k in ("CAPEVOLVE_HELPERS", "CAPEVOLVE_HELPERS_SPEC", "CAPEVOLVE_HELPERS_SEED", "CAPEVOLVE_HELPER_GATE"):
        monkeypatch.delenv(k, raising=False)
    return _load()


def _spec(tmp_path: Path, *, extra: str = "", ids: str = "10452\n105-24\n", smoke: bool = True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "ids.txt").write_text(ids)
    spec = tmp_path / "capevolve.yaml"
    spec.write_text(textwrap.dedent(f"""\
        surface:
          executable_dirs: ["skills/*/scripts"]
        helpers:
          enabled: true
          smoke: {str(smoke).lower()}
          smoke_timeout: 30
          ids_file: {tmp_path / 'ids.txt'}
        """) + extra)
    return spec


def _tree(root: Path, script: str | None, name: str = "h.py") -> Path:
    (root / "skills" / "spreadsheet-helpers" / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "spreadsheet-helpers" / "SKILL.md").write_text(
        "---\nname: spreadsheet-helpers\ndescription: d\n---\n")
    if script is not None:
        (root / "skills" / "spreadsheet-helpers" / "scripts" / name).write_text(script)
    return root


@pytest.fixture
def on(mod, tmp_path, monkeypatch):
    """The gate on, as an external caller sets it up: helpers on, a spec, an explicit seed."""
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg")))
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(_tree(tmp_path / "seed", None)))
    return mod


def _task(mod):
    return mod.Task(id="10452", input={"instruction": "", "spreadsheet_path": "", "instruction_type": "",
                                       "answer_position": "A1"})


@pytest.fixture
def no_llm(monkeypatch):
    fake = types.ModuleType("litellm")
    fake.completion = lambda *a, **k: pytest.fail("no LLM call may be made")
    monkeypatch.setitem(sys.modules, "litellm", fake)


# ---- off unless asked for --------------------------------------------------------------------------

def test_without_the_spec_env_it_is_off_and_never_reads_anything(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    calls = []
    monkeypatch.setattr(helper_gate, "gate", lambda *a, **k: calls.append(1))
    mod.Adapter()
    assert mod._external_gate_error(_tree(tmp_path / "c", BROKEN)) is None
    assert calls == []


def test_gate_false_in_the_spec_turns_it_off_and_warns(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg", extra="  gate: false\n")))
    assert mod._external_gate_error(_tree(tmp_path / "c", LEAK)) is None
    assert "helper gate is off" in capsys.readouterr().err


# ---- the shared gate's verdict ---------------------------------------------------------------------

@pytest.mark.parametrize("script,expected", [(CLEAN, None), (LEAK, "helper_lint"), (BROKEN, "helper_smoke")])
def test_the_adapter_and_the_core_gate_agree(on, tmp_path, script, expected):
    cand = _tree(tmp_path / "c", script)
    cfg = helpers.resolve({"surface": {"executable_dirs": ["skills/*/scripts"]},
                           "helpers": {"enabled": True, "smoke_timeout": 30,
                                       "ids_file": str(tmp_path / "cfg" / "ids.txt")}})
    seed = Path(os.environ["CAPEVOLVE_HELPERS_SEED"])
    core = helper_gate.gate(cand, cfg, parent=seed, seed=seed)
    assert next((c["name"] for c in core["checks"] if not c["ok"]), None) == expected
    err = on._external_gate_error(cand)
    if expected is None:
        assert err is None
    else:
        assert err.startswith("CANDIDATE_HELPER_GATE") and f"[{expected}]" in err


def test_a_helper_the_seed_already_ships_is_not_blamed_on_the_candidate(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg", smoke=False)))
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(_tree(tmp_path / "seed", LEAK)))
    assert mod._external_gate_error(_tree(tmp_path / "same", LEAK)) is None
    assert mod._external_gate_error(_tree(tmp_path / "changed", 'ID = "10452"\n'))


# ---- a config that cannot run stops the caller -------------------------------------------------------

def test_the_spec_enabling_helpers_the_agent_will_not_load_is_refused(mod, tmp_path, monkeypatch):
    # Eran on #954: the gate must check exactly what the loader loads, and run_target loads helpers only
    # when CAPEVOLVE_HELPERS says so
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg")))
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(_tree(tmp_path / "seed", None)))
    with pytest.raises(mod.HelperGateConfigError, match="CAPEVOLVE_HELPERS"):
        mod.Adapter()


def test_the_env_switching_helpers_off_keeps_the_gate_off(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "0")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg")))
    mod.Adapter()
    assert mod._external_gate_error(_tree(tmp_path / "c", LEAK)) is None


def test_the_seed_is_never_guessed(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg")))
    with pytest.raises(mod.HelperGateConfigError, match="CAPEVOLVE_HELPERS_SEED"):
        mod.Adapter()
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(tmp_path / "no_such_seed"))
    with pytest.raises(mod.HelperGateConfigError, match="seed"):
        mod.Adapter()


@pytest.mark.parametrize("breakage,match", [
    ("missing_spec", "CAPEVOLVE_HELPERS_SPEC"),
    ("missing_ids_file", "ids_file"),
    ("unknown_key", "no_such_key"),
])
def test_a_broken_config_raises_when_the_adapter_is_created(on, tmp_path, monkeypatch, breakage, match):
    spec = Path(os.environ["CAPEVOLVE_HELPERS_SPEC"])
    if breakage == "missing_spec":
        monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(tmp_path / "nope.yaml"))
    elif breakage == "missing_ids_file":
        (spec.parent / "ids.txt").unlink()
    else:
        spec.write_text(spec.read_text() + "  no_such_key: 1\n")
    with pytest.raises(on.HelperGateConfigError, match=match):
        on.Adapter()


def test_live_raises_when_the_config_breaks_mid_run(on, tmp_path, monkeypatch):
    adapter = on.Adapter()
    Path(os.environ["CAPEVOLVE_HELPERS_SPEC"]).unlink()
    monkeypatch.setattr(on, "_task_template_error", lambda ctx: None)
    with pytest.raises(on.HelperGateConfigError):
        with adapter.live(_tree(tmp_path / "c", CLEAN)):
            pass


# ---- run_target --------------------------------------------------------------------------------------

def test_run_target_scores_a_refused_candidate_0_without_an_llm_call(on, tmp_path, monkeypatch, no_llm):
    monkeypatch.setattr(on, "_task_template_error", lambda ctx: None)
    r = on.Adapter().run_target(_task(on), _tree(tmp_path / "c", LEAK), seed=0)
    assert r.error.startswith("CANDIDATE_HELPER_GATE")
    assert r.metadata == {"error_kind": "candidate", "helper_gate": "failed"}


def test_run_target_reports_a_config_broken_mid_run_as_infra_not_as_a_0(on, tmp_path, monkeypatch, no_llm):
    adapter = on.Adapter()
    (Path(os.environ["CAPEVOLVE_HELPERS_SPEC"]).parent / "ids.txt").unlink()
    monkeypatch.setattr(on, "_task_template_error", lambda ctx: None)
    r = adapter.run_target(_task(on), _tree(tmp_path / "c", CLEAN), seed=0)
    assert r.error.startswith("HELPER_GATE_CONFIG_ERROR") and "ids_file" in r.error
    assert r.metadata == {"error_kind": "infra", "helper_gate": "config_error"}


def test_an_unreadable_helper_file_is_the_candidates_fault(on, tmp_path):
    cand = _tree(tmp_path / "c", CLEAN)
    f = cand / "skills" / "spreadsheet-helpers" / "scripts" / "h.py"
    f.chmod(0)
    try:
        if os.access(f, os.R_OK):
            pytest.skip("running with permissions that ignore the file mode")
        err = on._external_gate_error(cand)
        assert err and err.startswith("CANDIDATE_HELPER_GATE") and "cannot be read" in err
    finally:
        f.chmod(0o644)


# ---- the verdict cache ---------------------------------------------------------------------------------

@pytest.fixture
def counted(on, monkeypatch):
    calls = []
    real = helper_gate.gate
    monkeypatch.setattr(helper_gate, "gate", lambda cand, *a, **k: calls.append(Path(cand).name) or real(cand, *a, **k))
    return on, calls


def test_one_check_per_tree_not_per_rollout(counted, tmp_path):
    on, calls = counted
    cand = _tree(tmp_path / "c", CLEAN)
    for _ in range(4):
        assert on._external_gate_error(cand) is None
    assert calls == ["c"]


def test_the_config_is_parsed_once_not_per_rollout(on, tmp_path, monkeypatch):
    import cap_evolve.specfile as sf
    reads = []
    real = sf.read_yaml
    monkeypatch.setattr(sf, "read_yaml", lambda *a, **k: reads.append(1) or real(*a, **k))
    cand = _tree(tmp_path / "c", CLEAN)
    for _ in range(4):
        on._external_gate_error(cand)
    assert len(reads) == 1


@pytest.mark.parametrize("where", ["nested_helper", "file_outside_the_helper_dirs"])
def test_trees_that_differ_anywhere_do_not_share_a_verdict(on, tmp_path, where):
    clean = _tree(tmp_path / "clean", CLEAN)
    other = _tree(tmp_path / "other", CLEAN)
    if where == "nested_helper":
        (other / "skills" / "spreadsheet-helpers" / "scripts" / "lib").mkdir()
        (other / "skills" / "spreadsheet-helpers" / "scripts" / "lib" / "inner.py").write_text(LEAK)
    else:
        (other / "run.sh").write_text("echo hi\n")         # the surface check refuses it
    assert on._external_gate_error(clean) is None
    assert on._external_gate_error(other), "a tree must not reuse another tree's verdict"


def test_editing_the_ids_file_resets_the_verdict(on, tmp_path):
    # the spec does not change, only the ids_file it names (Eran on #954)
    cand = _tree(tmp_path / "c", 'X = "77-7"\n')
    assert on._external_gate_error(cand) is None
    (Path(os.environ["CAPEVOLVE_HELPERS_SPEC"]).parent / "ids.txt").write_text("77-7\n")
    assert on._external_gate_error(cand)


def test_changing_the_seed_resets_the_verdict(mod, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SPEC", str(_spec(tmp_path / "cfg", smoke=False)))
    cand = _tree(tmp_path / "c", LEAK)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(_tree(tmp_path / "empty_seed", None)))
    assert mod._external_gate_error(cand)
    monkeypatch.setenv("CAPEVOLVE_HELPERS_SEED", str(_tree(tmp_path / "leaky_seed", LEAK)))
    assert mod._external_gate_error(cand) is None


def test_changing_the_config_resets_the_verdict(on, tmp_path, monkeypatch):
    cand = _tree(tmp_path / "c", LEAK)
    assert on._external_gate_error(cand)
    spec = Path(os.environ["CAPEVOLVE_HELPERS_SPEC"])
    spec.write_text(spec.read_text() + "  lint: false\n")
    os.utime(spec, ns=(spec.stat().st_atime_ns, spec.stat().st_mtime_ns + 10**9))  # a new mtime on any FS
    assert on._external_gate_error(cand) is None


def test_concurrent_rollouts_of_one_tree_run_one_check(counted, tmp_path):
    on, calls = counted
    cand = _tree(tmp_path / "c", CLEAN)
    out = []
    ts = [threading.Thread(target=lambda: out.append(on._external_gate_error(cand))) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert out == [None] * 8 and calls == ["c"]


def test_a_slow_check_does_not_block_other_trees(on, tmp_path, monkeypatch):
    # a lock per tree, not one global lock (Eran on #954)
    release, a_started = threading.Event(), threading.Event()
    real = helper_gate.gate

    def gate(cand, *a, **k):
        if Path(cand).name == "a":
            a_started.set()
            assert release.wait(60)
        return real(cand, *a, **k)

    monkeypatch.setattr(helper_gate, "gate", gate)
    # different contents: two identical trees share one key, and so (correctly) one check
    a, b = _tree(tmp_path / "a", CLEAN), _tree(tmp_path / "b", "def g(x):\n    return x\n")
    ta = threading.Thread(target=on._external_gate_error, args=(a,))
    ta.start()
    assert a_started.wait(60)
    out = []
    tb = threading.Thread(target=lambda: out.append(on._external_gate_error(b)))
    try:
        tb.start()
        tb.join(30)
        assert out == [None], "tree b waited for tree a's check"   # done while tree a's check is still held
    finally:
        release.set()
        ta.join(60)
        tb.join(60)


def test_identical_trees_share_one_check(counted, tmp_path):
    on, calls = counted
    assert on._external_gate_error(_tree(tmp_path / "a", CLEAN)) is None
    assert on._external_gate_error(_tree(tmp_path / "b", CLEAN)) is None
    assert calls == ["a"]
