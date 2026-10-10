"""#708: deterministic pre-gate. The regression fixture is the REAL cand_10 (run_20261008_150326):
its composite ``update_reservation_cabin`` called ``update_reservation_flights`` internally, so
tau2's grader saw no write and scored db_match=0 after 278 rollouts. Fixtures are verbatim
excerpts under core/tests/fixtures/pregate/ (seed/, cand_10/, cand10_task14_t1.json)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import pregate  # noqa: E402

FX = Path(__file__).parent / "fixtures" / "pregate"
SEED, CAND = FX / "seed", FX / "cand_10"


def test_cand10_hidden_write_is_caught_statically():
    r = pregate.hidden_writes_dirs(CAND, SEED)
    assert not r["ok"]
    assert "update_reservation_cabin calls write tool update_reservation_flights" in r["detail"]
    assert "update_reservation_baggages" in r["detail"]


def test_seed_and_unchanged_composites_pass():
    assert pregate.hidden_writes_dirs(SEED, None)["ok"]
    # same bytes as parent: a composite the parent already had is not this candidate's fault
    assert pregate.hidden_writes_dirs(CAND, CAND)["ok"]


def test_getattr_constant_is_resolved_computed_only_warns():
    src = ("class T:\n"
           "    @is_tool(ToolType.WRITE)\n    def a(self): pass\n"
           "    @is_tool(ToolType.WRITE)\n    def b(self):\n        return getattr(self, 'a')()\n"
           "    @is_tool(ToolType.WRITE)\n    def c(self, n):\n        return getattr(self, n)()\n")
    r = pregate.hidden_writes(src)
    assert not r["ok"] and "b calls write tool a" in r["detail"]
    assert r["warnings"] == ["c: getattr with a computed name (cannot verify)"]


def test_read_calling_read_and_write_calling_read_are_fine():
    src = ("class T:\n"
           "    @is_tool(ToolType.READ)\n    def r1(self): pass\n"
           "    @is_tool(ToolType.WRITE)\n    def w(self):\n        return self.r1()\n")
    assert pregate.hidden_writes(src)["ok"]


def test_static_flags_syntax_error_and_policy_growth(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "t.py").write_text("def f(:\n")
    r = pregate.static_check(tmp_path)
    assert not r["ok"] and "t.py" in r["detail"]
    # cand_10's policy grew ~42%: only a WARNING by default (big coherent edits are wanted) ...
    r = pregate.static_check(CAND, SEED)
    assert r["ok"] and "policy grew +42%" in r["warnings"][0]
    # ... a failure only when a cap is set explicitly
    assert not pregate.static_check(CAND, SEED, max_growth=0.3)["ok"]
    assert pregate.static_check(CAND, SEED, max_growth=0.5)["ok"]
    assert pregate.static_check(SEED, SEED)["ok"]


class _Kit:
    """Minimal toolkit: write tools mutate ``db``; ``bad`` makes the candidate diverge."""

    def __init__(self, bad=False):
        self.db, self.bad = {}, bad

    def get_reservation_details(self, reservation_id):
        return {"id": reservation_id}

    def update_reservation_flights(self, reservation_id, cabin):
        if self.bad:
            raise ValueError("cannot change")
        self.db[reservation_id] = cabin

    def get_db_hash(self):
        return json.dumps(self.db, sort_keys=True)


CALLS = [{"name": "get_reservation_details", "args": {"reservation_id": "R"}},
         {"name": "update_reservation_flights", "args": {"reservation_id": "R", "cabin": "business"}}]


def test_replay_equal_and_divergent():
    ok = pregate.replay(_Kit, _Kit, CALLS)
    assert ok["ok"], ok
    bad = pregate.replay(lambda: _Kit(bad=True), _Kit, CALLS)
    assert not bad["ok"]
    assert "call 1 update_reservation_flights" in bad["detail"]
    assert "successful write calls differ" in bad["detail"]
    assert pregate.replay(_Kit, _Kit, [])["skipped"]


def test_replay_reads_real_cand10_trace_calls():
    calls = pregate.trace_agent_calls(FX / "cand10_task14_t1.json")
    assert calls[-1]["name"] == "update_reservation_cabin"
    assert [c["name"] for c in calls][:2] == ["get_user_details", "get_reservation_details"]


def test_tool_smoke_new_exception_fails_and_missing_fixtures_skip():
    rows = [{"tool": "update_reservation_flights", "args": {"reservation_id": "R", "cabin": "x"},
             "result": "{}"}]
    assert not pregate.tool_smoke(_Kit(bad=True), rows)["ok"]
    assert pregate.tool_smoke(_Kit(), rows)["ok"]
    assert pregate.tool_smoke(_Kit(), rows, tools={"other"})["skipped"]


def test_run_end_to_end_cand10_fails_seed_passes_and_skips_cleanly():
    res = pregate.run(CAND, SEED)
    assert not res["ok"] and "[hidden_writes]" in res["failure"]
    assert "[static]" not in res["failure"] and "policy grew" in res["warnings"][0]
    assert {c["name"] for c in res["checks"] if c["skipped"]} == {"tool_smoke", "replay"}
    assert pregate.run(SEED, SEED)["ok"]


def test_cli_exit_code(tmp_path, capsys):
    assert pregate.main(["--candidate", str(CAND), "--parent", str(SEED)]) == 1
    assert pregate.main(["--candidate", str(SEED), "--parent", str(SEED)]) == 0


def test_ablation_switch(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_PREGATE", raising=False)
    assert pregate.enabled({}) and pregate.enabled(None)
    assert not pregate.enabled({"ablation": {"pregate": False}})
    monkeypatch.setenv("CAPEVOLVE_PREGATE", "off")
    assert not pregate.enabled({"ablation": {"pregate": True}})


def _tau2_python():
    import os
    import shutil
    if os.environ.get("CAPEVOLVE_TAU2_PYTHON"):
        return os.environ["CAPEVOLVE_TAU2_PYTHON"]
    for d in REPO.parents:
        if (d / ".venv-tau2" / "bin" / "python").exists():
            return str(d / ".venv-tau2" / "bin" / "python")
    return shutil.which("python-tau2")


def test_smoke_and_replay_are_live_on_real_tau2_toolkit(tmp_path):
    """Needs tau2 importable: set CAPEVOLVE_TAU2_PYTHON=<.venv-tau2>/bin/python (auto-found in a
    parent dir's .venv-tau2); otherwise skipped."""
    import subprocess

    import pytest
    py = _tau2_python()
    if not py or subprocess.run([py, "-c", "import tau2"], capture_output=True).returncode:
        pytest.skip("tau2 not importable: set CAPEVOLVE_TAU2_PYTHON to the .venv-tau2 python")
    fx = tmp_path / "fx.jsonl"
    fx.write_text(json.dumps({"tool": "get_all_reservations_for_user", "result": "[]",
                              "args": {"user_id": "mohamed_silva_9265"}}) + "\n")
    ro = tmp_path / "ro.json"
    ro.write_text(json.dumps({"trace": [{"role": "assistant", "tool_calls": [
        {"id": "1", "name": "get_user_details", "arguments": {"user_id": "mohamed_silva_9265"}},
        {"id": "2", "name": "get_reservation_details", "arguments": {"reservation_id": "K1NW8N"}}]}]}))
    adapter = REPO / "examples" / "tau2_airline" / "adapters" / "adapter.py"

    def go(trace):
        p = subprocess.run([py, str(REPO / "skills/algorithms/agent-optimize/scripts/pregate.py"),
                            "--candidate", str(CAND), "--parent", str(SEED), "--fixtures", str(fx),
                            "--toolkit", f"{adapter}:pregate_toolkit", "--trace", str(trace)],
                           capture_output=True, text=True)
        return {c["name"]: c for c in json.loads(p.stdout)["checks"]}

    c = go(ro)
    assert not c["tool_smoke"]["skipped"] and c["tool_smoke"]["ok"], c["tool_smoke"]
    assert not c["replay"]["skipped"] and c["replay"]["ok"], c["replay"]
    assert not c["hidden_writes"]["ok"]  # cand_10 is still caught by the AST scan
    # the real failing trace calls a tool the parent lacks: replay reports the divergence
    c = go(FX / "cand10_task14_t1.json")
    assert not c["replay"]["ok"] and "update_reservation_cabin" in c["replay"]["detail"]
