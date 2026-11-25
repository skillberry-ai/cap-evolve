"""agent-optimize measure.py must disclose a test-seal override, not claim "sealed now (once)"."""

import importlib.util
import json
import sys
from pathlib import Path

from cap_evolve.rundir import RunDir
from cap_evolve.splits import make_splits

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _measure(tmp_path, monkeypatch, *, override, presealed=False):
    rd = RunDir.create(tmp_path)
    rd.write_splits(make_splits([f"t{i}" for i in range(8)], seed=0))
    sr = {"split": "test", "reward": 0.5, "stderr": 0.1, "n_tasks": 2}
    fin = {"test": sr, "test_baseline": sr, "test_delta": 0.0}

    def fake_finalize(adapter, **kw):  # toy: no model, just the seal bookkeeping
        if override:
            rd._record_test_rescore_override(1)
        (rd.root / "final.json").write_text(json.dumps(fin), encoding="utf-8")
        rd.commit_test()
        return fin

    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("measure_override_test", SCRIPTS / "measure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.harness, "finalize", fake_finalize)
    monkeypatch.setattr(mod, "load_adapter", lambda project: object())
    if presealed:
        fake_finalize(None)
    assert mod.main(["--run-dir", str(rd.root), "--project", str(tmp_path),
                     "--train", "off"]) == 0
    payload = json.loads((rd.root / "measure.json").read_text(encoding="utf-8"))
    return {r["split"]: r for r in payload["splits"]}["test"], payload


def test_override_is_disclosed_when_sealing_now(tmp_path, monkeypatch):
    row, payload = _measure(tmp_path, monkeypatch, override=True)
    assert row["status"] != "sealed now (once)"
    assert "re-scored 1 time(s)" in row["status"]
    assert "CAPEVOLVE_ALLOW_TEST_RESCORE" not in json.dumps(payload)
    assert payload["test_rescore_override"]["used"] is True
    assert payload["test_rescore_override"]["count"] == 1


def test_override_is_disclosed_when_already_sealed(tmp_path, monkeypatch):
    row, payload = _measure(tmp_path, monkeypatch, override=True, presealed=True)
    assert "re-scored 1 time(s)" in row["status"]
    assert payload["test_rescore_override"]["count"] == 1


def test_normal_run_still_says_sealed_now_once(tmp_path, monkeypatch):
    row, payload = _measure(tmp_path, monkeypatch, override=False)
    assert row["status"] == "sealed now (once)"
    assert "test_rescore_override" not in payload
