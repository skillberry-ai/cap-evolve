"""A reused test split (#761) must show in report, measure.py and the dashboard (T-90)."""
import json

from cap_evolve.dashboard import reduce_run, write_dashboard
from cap_evolve.rundir import RunDir
from cap_evolve.splits import make_splits
from test_measure_test_seal_override import _measure  # noqa: F401
from test_report_test_seal_override import _report


def _run(base, ts, ids):
    rd = RunDir.create(base, ts=ts)
    rd.write_splits(make_splits(ids, seed=0))
    (rd.root / "final.json").write_text(
        json.dumps({"test": {"reward": 0.5}, "best_id": rd.best_id}), encoding="utf-8")
    rd.begin_test_attempt()
    rd.reserve_test()
    rd.commit_test()
    return rd


def test_report_and_dashboard_show_reuse(tmp_path):
    ids = [f"t{i}" for i in range(8)]
    a = _run(tmp_path, "a", ids)
    b = _run(tmp_path, "b", ids)
    md, summary = _report(b)
    assert "scored exactly once" not in md
    assert "already scored by 1 other run(s)" in md and "run_a" in md
    assert summary["test_reuse_count"] == 1
    assert reduce_run(b)["summary"]["test_reuse_count"] == 1
    html = write_dashboard(b).read_text(encoding="utf-8")
    assert "WARNING: this test split was already scored by" in html
    # first run unchanged
    md_a, summary_a = _report(a)
    assert "scored exactly once" in md_a and "test_reuse_count" not in summary_a
    assert "test_reuse_count" not in reduce_run(a)["summary"]


def test_measure_shows_reuse(tmp_path, monkeypatch):
    ids = [f"t{i}" for i in range(8)]
    _run(tmp_path, "a", ids)
    import test_measure_test_seal_override as m
    # second run under the same base, already sealed -> measure reports final.json
    b = _run(tmp_path, "b", ids)
    sr = {"split": "test", "reward": 0.5, "stderr": 0.1, "n_tasks": 2}
    fin = json.loads((b.root / "final.json").read_text())
    fin.update({"test": sr, "test_baseline": sr, "test_delta": 0.0})
    (b.root / "final.json").write_text(json.dumps(fin), encoding="utf-8")
    monkeypatch.syspath_prepend(str(m.SCRIPTS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("measure_reuse_test", m.SCRIPTS / "measure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--run-dir", str(b.root), "--project", str(tmp_path), "--train", "off"]) == 0
    payload = json.loads((b.root / "measure.json").read_text())
    row = {r["split"]: r for r in payload["splits"]}["test"]
    assert payload["test_reuse_count"] == 1
    assert "already scored by 1 other run(s)" in row["status"]
