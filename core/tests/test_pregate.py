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

import pytest  # noqa: E402
import pregate  # noqa: E402

FX = Path(__file__).parent / "fixtures" / "pregate"
SEED, CAND = FX / "seed", FX / "cand_10"


def test_cand10_hidden_write_is_caught_statically():
    r = pregate.hidden_writes_dirs(CAND, SEED)
    assert not r["ok"]
    assert "update_reservation_cabin -> update_reservation_flights" in r["detail"]
    assert "update_reservation_cabin -> update_reservation_baggages" in r["detail"]


def test_seed_unchanged_composites_and_missing_parent():
    assert pregate.hidden_writes_dirs(SEED, SEED)["ok"]
    # same bytes as parent: a composite the parent already had is not this candidate's fault
    assert pregate.hidden_writes_dirs(CAND, CAND)["ok"]
    # no parent: delta checks are skipped with a warning, existing composites are not flagged
    r = pregate.hidden_writes_dirs(CAND, None)
    assert r["ok"] and r["skipped"] and r["warnings"]


_BASE = ("class T:\n"
         "    @is_tool(ToolType.WRITE)\n    def update_a(self, x): pass\n"
         "    def _helper(self, x):\n        return self.update_a(x)\n")


def _hw(body, extra="", head="", parent=_BASE):
    """Candidate = _BASE + a new write tool update_b whose body is ``body``."""
    src = head + _BASE + extra + ("    @is_tool(ToolType.WRITE)\n    def update_b(self, x):\n"
                                  + "".join(f"        {ln}\n" for ln in body.split("\n")))
    return pregate.hidden_writes(src, parent)


@pytest.mark.parametrize("body,head", [
    ("return self.update_a(x)", ""),                                  # direct (the cand_10 form)
    ("return self._helper(x)", ""),                                   # private helper
    ("return type(self).update_a(self, x)", ""),                      # type(self).m
    ("return self.helper.update_a(x)", ""),                           # attribute chain
    ("m = self.update_a\nreturn m(x)", ""),                           # alias
    ("return {'a': self.update_a}['a'](x)", ""),                      # dispatch dict
    ("return getattr(self, 'update_' + 'a')(x)", ""),                 # folded getattr name
    ("return update_z(x)", "from other import update_z\n"),           # bare imported write
], ids=["direct", "private_helper", "type_self", "chain", "alias", "dispatch", "getattr_fold", "bare_import"])
def test_every_bypass_form_is_flagged(body, head):
    r = _hw(body, head=head)
    assert not r["ok"] and ("update_a" in r["detail"] or "update_z" in r["detail"]), r


def test_computed_name_is_a_failure_not_a_warning():
    for body in ("return getattr(self, x)()", "return eval(x)", "return globals()[x]()"):
        r = _hw(body)
        assert not r["ok"] and "unresolvable" in r["detail"], body


def test_transitive_through_two_helpers():
    r = _hw("return self._h1(x)", extra="    def _h1(self, x):\n        return self._helper(x)\n")
    assert not r["ok"] and "update_b -> _h1 -> _helper -> update_a" in r["detail"]


def test_plain_public_helpers_and_reads_are_not_writes():
    extra = ("    def format_reservation(self, r): return str(r)\n"
             "    @is_tool(ToolType.READ)\n    def get_r(self): pass\n")
    assert _hw("return self.format_reservation(self.get_r())", extra=extra)["ok"]


def test_docstring_edit_to_existing_composite_is_not_blamed():
    parent = _BASE + ("    @is_tool(ToolType.WRITE)\n    def update_b(self, x):\n"
                      "        return self.update_a(x)\n")
    cand = parent.replace("def update_b(self, x):\n", 'def update_b(self, x):\n        """doc"""\n')
    assert pregate.hidden_writes(cand, parent)["ok"]


def test_same_named_methods_in_different_classes_do_not_collide():
    src = ("class A:\n    @is_tool(ToolType.WRITE)\n    def update_x(self): pass\n"
           "    @is_tool(ToolType.WRITE)\n    def update_y(self):\n        return self.run()\n"
           "    def run(self): return 1\n"
           "class B:\n    def run(self):\n        return self.update_x()\n"
           "    @is_tool(ToolType.WRITE)\n    def update_x(self): pass\n")
    assert pregate.hidden_writes(src, "")["ok"]


def test_explicit_write_tools_are_authoritative():
    src = "class T:\n    def zap(self): pass\n    def update_q(self):\n        return self.zap()\n"
    assert not pregate.hidden_writes(src, "", explicit={"zap", "update_q"})["ok"]
    assert pregate.hidden_writes(src, "", explicit={"other"})["ok"]  # no prefix guessing then


def test_read_calling_read_and_write_calling_read_are_fine():
    src = ("class T:\n"
           "    @is_tool(ToolType.READ)\n    def r1(self): pass\n"
           "    @is_tool(ToolType.WRITE)\n    def w(self):\n        return self.r1()\n")
    assert pregate.hidden_writes(src, "")["ok"]


def test_infra_errors_never_crash_and_strict_fails(tmp_path):
    fx = tmp_path / "fx.jsonl"
    fx.write_text("{not json\n")
    for tk in ("no_such_module_xyz:make", "/nonexistent/adapter.py:f"):
        res = pregate.run(CAND, SEED, fixtures=fx, toolkit=tk)
        assert "[hidden_writes]" in res["failure"]            # the real verdict is never lost
        errs = [c for c in res["checks"] if c.get("error")]
        assert errs and all(c["ok"] for c in errs)           # fail-open ...
        assert any("errored" in w for w in res["warnings"])  # ... but loud
    res = pregate.run(SEED, SEED, fixtures=fx, toolkit="no_such_module_xyz:make", strict=True)
    assert not res["ok"] and "infra error" in res["failure"]


def test_replay_changed_tools_are_info_only():
    # candidate's update_reservation_flights is "fixed" (raises); parent's succeeds
    r = pregate.replay(lambda: _Kit(bad=True), _Kit, CALLS, changed={"update_reservation_flights"})
    assert r["ok"] and r["info"]
    assert not pregate.replay(lambda: _Kit(bad=True), _Kit, CALLS, changed={"other"})["ok"]


def test_ablation_key_is_optimizer_ablation_with_legacy_fallback(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_PREGATE", raising=False)
    assert not pregate.enabled({"optimizer": {"ablation": {"pregate": False}}})
    assert not pregate.enabled({"ablation": {"pregate": False}})
    assert pregate.enabled({"optimizer": {"ablation": {"pregate": True}}, "ablation": {"pregate": False}})


def test_static_ignores_files_outside_tools(tmp_path):
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "py2.py").write_text("print 'x'\n")
    assert pregate.static_check(tmp_path)["ok"]

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
    # the real failing trace calls a tool the parent lacks (a CHANGED tool): info only, not a failure
    c = go(FX / "cand10_task14_t1.json")
    assert c["replay"]["ok"] and "update_reservation_cabin" in " ".join(c["replay"]["info"])
