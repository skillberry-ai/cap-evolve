"""v2: the pregate ``helper_smoke`` stage. It runs real subprocesses (no model, no network)."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

from cap_evolve import helper_smoke, helpers  # noqa: E402
import pregate  # noqa: E402

REL = "skills/fmt/scripts/norm.py"
CFG = helpers.resolve({"helpers": {"enabled": True, "smoke_timeout": 30}})

GOOD = '''import json, sys

def normalise(xs):
    return sorted(set(xs))

if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    json.dump(normalise(data), open(sys.argv[2], "w"))
    print("done")
'''
ROW = {"helper": REL, "argv": ["{ws}/in.json", "{ws}/out.json"], "files": {"in.json": "[3, 1, 2, 1]"},
       "outputs": ["out.json"], "id": "t1"}


def _cand(tmp_path, body, name="c"):
    p = tmp_path / name / REL
    p.parent.mkdir(parents=True)
    p.write_text(body, encoding="utf-8")
    return tmp_path / name


def _smoke(c, rows=(ROW,), **kw):
    return helper_smoke.run_smoke(c, {**CFG, **kw}, fixtures=list(rows))


def test_a_good_helper_passes_with_two_runs_per_fixture(tmp_path):
    r = _smoke(_cand(tmp_path, GOOD))
    assert r["ok"], r["detail"]
    assert r["runs"] == 3          # import + 2 runs


def test_call_fixtures_and_return_value_determinism(tmp_path):
    row = {"helper": REL, "kind": "call", "call": "normalise", "args": [[2, 1, 2]]}
    assert _smoke(_cand(tmp_path, GOOD), [row])["ok"]
    bad = _cand(tmp_path, "import random\n\ndef normalise(xs):\n    return random.random()\n", "c2")
    r = _smoke(bad, [row])
    assert not r["ok"] and "not deterministic" in r["detail"]


def test_hash_order_nondeterminism_is_caught(tmp_path):
    src = ("import sys\n\ndef normalise(xs):\n    return ','.join({str(x) + 'a' for x in xs})\n"
           "if __name__ == '__main__':\n    print(normalise(range(12)))\n")
    r = _smoke(_cand(tmp_path, src), [{"helper": REL, "outputs": []}])
    assert not r["ok"] and "not deterministic" in r["detail"]


def test_import_error_and_crash_are_reported(tmp_path):
    assert "import" in _smoke(_cand(tmp_path, "import not_a_real_module_xyz\n"), [])["detail"]
    r = _smoke(_cand(tmp_path, "raise SystemExit(3)\n", "c2"), [ROW])
    assert not r["ok"]
    r = _smoke(_cand(tmp_path, GOOD, "c3"), [{**ROW, "files": {"in.json": "not json"}}])
    assert not r["ok"] and "JSONDecodeError" in r["detail"]


def test_network_is_blocked_even_if_the_helper_swallows_the_error(tmp_path):
    src = ("import socket\ntry:\n    socket.create_connection(('127.0.0.1', 9), timeout=1)\n"
           "except Exception:\n    pass\n")
    r = _smoke(_cand(tmp_path, src), [])
    assert not r["ok"] and "network" in r["detail"]


def test_dns_is_blocked(tmp_path):
    r = _smoke(_cand(tmp_path, "import socket\nsocket.getaddrinfo('example.com', 80)\n"), [])
    assert not r["ok"] and "network" in r["detail"]


def test_subprocess_is_blocked(tmp_path):
    r = _smoke(_cand(tmp_path, "import subprocess\ntry:\n    subprocess.run(['true'])\nexcept Exception:\n    pass\n"), [])
    assert not r["ok"] and "process" in r["detail"]


def test_write_outside_declared_outputs_fails(tmp_path):
    r = _smoke(_cand(tmp_path, GOOD.replace("print(\"done\")", "open('stray.txt','w').write('x')")), [ROW])
    assert not r["ok"] and "declared outputs" in r["detail"]
    target = tmp_path / "elsewhere.txt"
    r2 = _smoke(_cand(tmp_path, f"open({str(target)!r}, 'w').write('x')\n", "c2"), [])
    assert not r2["ok"] and not target.exists()


def test_gold_and_evaluator_paths_cannot_be_read(tmp_path):
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "1_x_answer.xlsx").write_text("secret")
    src = f"try:\n    print(open({str(gold / '1_x_answer.xlsx')!r}).read())\nexcept Exception:\n    pass\n"
    r = _smoke(_cand(tmp_path, src), [{"helper": REL}])
    assert not r["ok"] and "evaluator/gold" in r["detail"]
    other = tmp_path / "ev"
    other.mkdir()
    (other / "notes.txt").write_text("secret")
    src2 = f"try:\n    open({str(other / 'notes.txt')!r}).read()\nexcept Exception:\n    pass\n"
    r2 = _smoke(_cand(tmp_path, src2, "c2"), [{"helper": REL}], deny_roots=[str(other)])
    assert not r2["ok"] and "protected path" in r2["detail"]


def test_a_fixture_cannot_be_sourced_from_gold(tmp_path):
    gold = tmp_path / "golden_dir"
    gold.mkdir()
    (gold / "a.xlsx").write_text("secret")
    row = {**ROW, "files": {"in.json": {"src": str(gold / "a.xlsx")}}}
    r = _smoke(_cand(tmp_path, GOOD), [row])
    assert not r["ok"] and "protected" in r["detail"]


def test_timeout_is_a_failure(tmp_path):
    r = _smoke(_cand(tmp_path, "import time\ntime.sleep(30)\n"), [], smoke_timeout=1)
    assert not r["ok"] and "timed out" in r["detail"]


def test_unchanged_files_are_not_rerun(tmp_path):
    p, c = _cand(tmp_path, GOOD, "p"), _cand(tmp_path, GOOD, "c")
    r = helper_smoke.run_smoke(c, CFG, parent=p, fixtures=[ROW])
    assert r["skipped"] and r["runs"] == 0


def test_fixtures_load_from_recorded_traces_and_jsonl(tmp_path):
    tr = tmp_path / "rollout.json"
    tr.write_text(json.dumps({"metadata": {"helper_fixtures": [ROW]}}), encoding="utf-8")
    fx = tmp_path / "fx.jsonl"
    fx.write_text(json.dumps({**ROW, "id": "t2"}) + "\n", encoding="utf-8")
    rows = helper_smoke.load_fixtures(fx, [tr, tmp_path / "missing.json"])
    assert [r["id"] for r in rows] == ["t2", "t1"]


def test_the_smoke_does_not_touch_the_host_network(tmp_path, monkeypatch):
    """The parent process never opens a socket either."""
    def boom(*a, **k):
        raise AssertionError("parent opened a socket")
    monkeypatch.setattr(socket, "socket", boom)
    assert _smoke(_cand(tmp_path, GOOD))["ok"]


# ---- the pregate wiring --------------------------------------------------------------------------
def _pregate(c, **helpers_cfg):
    return pregate.run(c, None, helpers={**CFG, **helpers_cfg})


def test_pregate_is_unchanged_when_helpers_are_off(tmp_path):
    c = _cand(tmp_path, "import socket\n")
    r = pregate.run(c, None)
    assert [x["name"] for x in r["checks"]] == ["static", "hidden_writes", "tool_smoke", "replay"]
    assert pregate.run(c, None, helpers={**CFG, "enabled": False})["ok"]


def test_pregate_runs_surface_lint_and_smoke_and_a_failure_costs_nothing(tmp_path):
    good = _pregate(_cand(tmp_path, GOOD))
    assert good["ok"], good["failure"]
    assert {"helper_surface", "helper_lint", "helper_smoke"} <= {c["name"] for c in good["checks"]}
    bad = _pregate(_cand(tmp_path, "import socket\n", "c2"))
    assert not bad["ok"] and "[helper_lint]" in bad["failure"]
    stray = _cand(tmp_path, GOOD, "c3")
    (stray / "elsewhere").mkdir()
    (stray / "elsewhere/x.py").write_text("x = 1\n")
    assert "[helper_surface]" in _pregate(stray)["failure"]


def test_pregate_cli_takes_the_resolved_config(tmp_path, capsys):
    c = _cand(tmp_path, "import subprocess\n")
    rc = pregate.main(["--candidate", str(c), "--helpers-config", json.dumps(CFG)])
    assert rc == 1 and "helper_lint" in capsys.readouterr().out
    assert pregate.main(["--candidate", str(c)]) == 0


# ---- review round: socket creation, more mutating calls, harvested fixtures ------------------------
def test_a_socket_is_never_created_so_sendmsg_cannot_send_without_connect(tmp_path):
    src = ("import socket\ntry:\n    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
           "    s.sendmsg([b'x'], [], 0, ('127.0.0.1', 9))\nexcept Exception:\n    pass\n")
    r = _smoke(_cand(tmp_path, src), [])
    assert not r["ok"] and "network" in r["detail"] and "socket.__new__" in r["detail"]


def test_a_computed_import_of_socket_is_stopped_at_run_time_too(tmp_path):
    src = ("import importlib\ntry:\n    m = importlib.import_module('soc' + 'ket')\n"
           "    m.socket(m.AF_INET, m.SOCK_DGRAM)\nexcept Exception:\n    pass\n")
    r = _smoke(_cand(tmp_path, src), [])
    assert not r["ok"] and "network" in r["detail"]


@pytest.mark.parametrize("call", ["os.utime(T, (0, 0))", "os.chown(T, -1, -1)", "os.mkfifo(T + '.fifo')",
                                  "os.mknod(T + '.node')"])
def test_utime_chown_mkfifo_mknod_outside_the_outputs_are_refused(tmp_path, call):
    target = tmp_path / "victim.txt"
    target.write_text("x")
    src = f"import os\nT = {str(target)!r}\ntry:\n    {call}\nexcept PermissionError:\n    pass\nexcept OSError:\n    pass\n"
    r = _smoke(_cand(tmp_path, src), [])
    assert not r["ok"] and "outside the declared outputs" in r["detail"]
    assert not (tmp_path / "victim.txt.fifo").exists() and not (tmp_path / "victim.txt.node").exists()


def test_recorded_helper_calls_become_deduplicated_call_fixtures(tmp_path):
    call = {"helper": REL, "call": "normalise", "args": [[3, 1, 1]], "kwargs": {}}
    t = tmp_path / "r.json"
    t.write_text(json.dumps({"task_id": "t1", "metadata": {"helper_calls": [call, call, {**call, "args": [[2]]}]}}))
    rows = helper_smoke.fixtures_from_traces([t])
    assert [r["args"] for r in rows] == [[[3, 1, 1]], [[2]]] and all(r["kind"] == "call" for r in rows)
    r = _smoke(_cand(tmp_path, GOOD), rows)
    assert r["ok"], r["detail"]


def test_fixture_traces_come_from_feedback_splits_only(tmp_path):
    for sp in ("feedback", "train", "confirm", "test", "val"):
        (tmp_path / sp).mkdir()
        (tmp_path / sp / f"t__cand_1__t0.json").write_text("{}")
    got = helper_smoke.fixture_traces(tmp_path, "cand_1")
    assert sorted(p.parent.name for p in got) == ["feedback", "train"]
    with pytest.raises(ValueError, match="never come from"):
        helper_smoke.fixture_traces(tmp_path, "cand_1", ("feedback", "confirm"))
    assert helper_smoke.fixture_traces(tmp_path, "other") == []


def test_importing_ctypes_transitively_is_not_a_foreign_code_violation(tmp_path):
    """`import ctypes` runs `PyDLL(None)` (a handle to the interpreter itself), which fires a
    `ctypes.dlopen` audit event; numpy, pandas and openpyxl import it. A helper whose only
    sin is a data-library import must pass, while loading a named shared object must not."""
    ok = _cand(tmp_path, "import ctypes\n\ndef f():\n    return 1\n", "c_ok")
    assert _smoke(ok)["ok"], _smoke(ok)["detail"]
    bad = _cand(tmp_path, "import ctypes\nctypes.CDLL('libc.so.6')\n", "c_bad")
    r = _smoke(bad)
    assert not r["ok"] and "foreign-code" in r["detail"]
