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
    # cand_10's policy grew ~42% over the seed's: over the default +30% cap, under a +50% cap
    assert "policy grew" in pregate.static_check(CAND, SEED)["detail"]
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
    res = pregate.run(CAND, SEED, max_growth=0.5)
    assert not res["ok"] and "[hidden_writes]" in res["failure"]
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
