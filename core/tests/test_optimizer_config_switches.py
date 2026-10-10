"""#712: the seven ablation switches resolve in ONE place with one precedence, every module that
used to read its own key now defers to it, and with all of them off the legacy round.py path is
byte-for-byte what main produced (fixture captured from main before this change)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(SCRIPTS))

from cap_evolve import objectives, optimizer_config as oc, posterior  # noqa: E402

KEYS = sorted(oc.DEFAULTS)


def _clean(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(f"CAPEVOLVE_{k.upper()}", raising=False)


@pytest.mark.parametrize("key", KEYS)
def test_precedence_env_then_optimizer_then_legacy_then_default(monkeypatch, key):
    _clean(monkeypatch)
    d = oc.DEFAULTS[key]
    assert oc.enabled(key, {}) is d and oc.enabled(key, None) is d
    legacy = {"ablation": {key: not d}}
    assert oc.enabled(key, legacy) is (not d)
    both = {"ablation": {key: not d}, "optimizer": {"ablation": {key: d}}}
    assert oc.enabled(key, both) is d, "optimizer.ablation beats the legacy top-level table"
    monkeypatch.setenv(f"CAPEVOLVE_{key.upper()}", "0" if d else "1")
    assert oc.enabled(key, both) is (not d), "env beats every spec table"
    monkeypatch.setenv(f"CAPEVOLVE_{key.upper()}", "off")
    assert oc.enabled(key, {}) is False


def test_each_switch_is_independent(monkeypatch):
    _clean(monkeypatch)
    for k in KEYS:
        spec = {"optimizer": {"ablation": {k: not oc.DEFAULTS[k]}}}
        got = oc.resolve(spec)
        assert {x for x in KEYS if got[x] != oc.DEFAULTS[x]} == {k}


def test_typos_and_non_booleans_are_rejected(monkeypatch):
    _clean(monkeypatch)
    for bad in ({"optimizer": {"ablation": {"pregte": False}}}, {"ablation": {"nope": True}},
                {"optimizer": {"ablation": {"pregate": "false"}}}):
        with pytest.raises(ValueError):
            oc.resolve(bad)
    monkeypatch.setenv("CAPEVOLVE_PREGATE", "maybe")
    with pytest.raises(ValueError):
        oc.enabled("pregate", {})
    with pytest.raises(ValueError):
        oc.enabled("nosuch", {})


def test_new_engine_needs_both_dag_parallel_and_active_eval(monkeypatch):
    _clean(monkeypatch)
    assert not oc.new_engine({}), "default: active_eval off => legacy ceremonies stay"
    assert oc.new_engine({"optimizer": {"ablation": {"active_eval": True}}})
    assert not oc.new_engine({"optimizer": {"ablation": {"active_eval": True, "dag_parallel": False}}})


def test_every_former_ad_hoc_reader_follows_the_resolver(monkeypatch):
    import pregate
    import importlib.util
    d = str(REPO / "skills/phases/diagnose/scripts")
    sys.path.insert(0, d)  # run.py imports its sibling cluster.py
    try:
        sp = importlib.util.spec_from_file_location("diag_run", d + "/run.py")
        diagnose_run = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(diagnose_run)
    finally:
        sys.path.remove(d)
        sys.modules.pop("cluster", None)
    _clean(monkeypatch)
    readers = {"active_eval": posterior.enabled, "cost_gating": objectives.cost_gating_enabled,
               "pregate": pregate.enabled}
    for key, fn in readers.items():
        d = oc.DEFAULTS[key]
        assert fn({}) is d, f"{key}: default preserved"
        assert fn({"optimizer": {"ablation": {key: not d}}}) is (not d)
        assert fn({"ablation": {key: not d}}) is (not d), "legacy top-level table honoured everywhere"
        monkeypatch.setenv(f"CAPEVOLVE_{key.upper()}", "1" if d is False else "0")
        assert fn({}) is (not d)
        monkeypatch.delenv(f"CAPEVOLVE_{key.upper()}")
    class _RD:  # failure_clustering_enabled reads the spec through spec_for_run
        pass
    monkeypatch.setattr("cap_evolve.specfile.spec_for_run",
                        lambda rd, p=None: {"optimizer": {"ablation": {"failure_clustering": False}}})
    assert diagnose_run.failure_clustering_enabled(_RD(), None) is False
    monkeypatch.setattr("cap_evolve.specfile.spec_for_run", lambda rd, p=None: {})
    assert diagnose_run.failure_clustering_enabled(_RD(), None) is True


def test_dag_parallel_off_records_no_parent_edge_in_prepare_candidate(tmp_path, monkeypatch):
    from test_round_requires_screen_ladder import _run, _staged_run_dir
    _clean(monkeypatch)
    run_dir, project, _ = _staged_run_dir(tmp_path)
    for tag, env in (("on_1", {}), ("off_1", {"CAPEVOLVE_DAG_PARALLEL": "0"})):
        p = _run([str(SCRIPTS / "prepare_candidate.py"), "-r", str(run_dir.root), "-t", tag], env)
        assert p.returncode == 0, p.stdout + p.stderr
    from cap_evolve import graph
    ids = [n["id"] for n in graph.read_nodes(run_dir)]
    assert ids == ["on_1"], "dag_parallel off => legacy: nothing recorded at creation"


def test_round_sibling_minimum_is_dropped_only_by_the_new_engine():
    import round as round_mod
    with pytest.raises(round_mod.SingleCandidateUnjustified):
        round_mod.sibling_justification(1, None, None)
    assert round_mod.sibling_justification(1, None, None, new_engine=True)[1] == "new_engine"
    assert round_mod.sibling_justification(3, None, None, new_engine=True) == (None, None)


def test_all_switches_off_round_py_is_bit_identical_to_main(tmp_path):
    """Golden captured from origin/main BEFORE this change (same staged run, same flags)."""
    from test_round_requires_screen_ladder import _JUSTIFY, _staged_run_dir
    run_dir, project, _ = _staged_run_dir(tmp_path)
    env = dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"), PYTHONHASHSEED="0",
               **{f"CAPEVOLVE_{k.upper()}": "0" for k in KEYS})
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1", "--n-trials", "1", *_JUSTIFY],
                       capture_output=True, text=True, env=env)
    tmp = str(tmp_path)
    nodes = [json.loads(ln) for ln in (run_dir.root / "graph.jsonl").read_text().splitlines()]
    got = json.dumps({"rc": p.returncode, "out": p.stdout.replace(tmp, "<TMP>"),
                      "stderr_tail": p.stderr[-300:].replace(tmp, "<TMP>"), "graph": nodes},
                     indent=1, sort_keys=True).replace(tmp, "<TMP>")
    want = (Path(__file__).parent / "fixtures" / "legacy_round_all_switches_off.json").read_text()
    assert json.loads(got) == json.loads(want)


def test_new_engine_round_needs_no_sibling_justification_and_no_null_control(tmp_path):
    """active_eval on (+ dag_parallel default on): one candidate, no justification, no ctl_null."""
    from test_round_requires_screen_ladder import _run, _staged_run_dir
    for engine, want_rc in (("1", 0), ("0", 2)):
        sub = tmp_path / engine
        sub.mkdir()
        run_dir, project, work = _staged_run_dir(sub)
        p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root), "--project", str(project),
                  "--candidates", "cand_1", "--n-trials", "1", "--skip-screen-justification", "t"],
                 {"CAPEVOLVE_ACTIVE_EVAL": engine})
        assert p.returncode == want_rc, p.stdout + p.stderr
        controls = [d.name for d in (run_dir.root / "work").iterdir() if d.name.startswith("ctl_null")]
        if engine == "1":
            assert controls == [], controls
