"""Secondary per-task metrics (e.g. spreadsheetbench's `hard_no_recalc`) reach metrics.jsonl and report.md.

They are recorded by the adapter on every Score, but the suite report only read `reward`, so a
second scoring of the same outputs was on disk yet invisible in every published artifact.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"


def _metrics():
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("_bench_metrics_secondary", LIB / "metrics.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bench_metrics_secondary"] = mod
    spec.loader.exec_module(mod)
    return mod


def _pt(tid, reward, no_recalc=None):
    metrics = [{"name": "hard_restriction", "value": reward, "primary": True, "direction": "higher"}]
    if no_recalc is not None:
        metrics.append({"name": "hard_no_recalc", "value": no_recalc, "primary": False,
                        "direction": "higher"})
    return {"task_id": tid, "reward": reward, "raw": {}, "metrics": metrics}


def _run_dir(tmp: Path, *, secondary: bool) -> Path:
    nr = (lambda v: v) if secondary else (lambda v: None)
    rd = tmp / "run_suite"
    rd.mkdir()
    val = {"split": "val", "reward": 0.5, "per_task": [_pt("v1", 1.0, nr(0.0)), _pt("v2", 0.0, nr(0.0))]}
    test = {"split": "test", "reward": 1.0, "per_task": [_pt("t1", 1.0, nr(0.0)), _pt("t2", 1.0, nr(1.0))]}
    (rd / "baseline.json").write_text(json.dumps({"val": val, "best_id": "seed"}))
    (rd / "final.json").write_text(json.dumps({
        "test": test, "test_baseline": test, "best_id": "seed", "baseline_id": "seed",
        "test_delta": 0.0, "seed": {"val": val, "test": test}, "best": {"val": val, "test": test},
    }))
    (rd / "state.json").write_text(json.dumps({"best_id": "seed", "spent": {}}))
    (rd / "events.jsonl").write_text("")
    return rd


def test_secondary_metrics_are_written_per_task_and_summarised_per_split(tmp_path):
    m = _metrics()
    jsonl = tmp_path / "metrics.jsonl"
    report = m.suite_report(str(_run_dir(tmp_path, secondary=True)), "spreadsheetbench",
                            "full_verified", "g", 0, jsonl_path=str(jsonl))
    rows = {r["task"]: r for r in map(json.loads, jsonl.read_text().splitlines())}
    assert rows["t1"]["metrics_opt"] == {"hard_no_recalc": 0.0}
    assert rows["t2"]["metrics_baseline"] == {"hard_no_recalc": 1.0}
    assert "### Metrics by candidate and split" in report
    assert "| seed | test | 2 | 1.0000 | 0.5000 |" in report
    assert "| seed | val | 2 | 0.5000 | 0.0000 |" in report


def test_benchmarks_without_secondary_metrics_keep_their_report(tmp_path):
    m = _metrics()
    jsonl = tmp_path / "metrics.jsonl"
    report = m.suite_report(str(_run_dir(tmp_path, secondary=False)), "tau2", "smoke", "g", 0,
                            jsonl_path=str(jsonl))
    assert "Metrics by candidate" not in report
    assert all("metrics_opt" not in json.loads(l) for l in jsonl.read_text().splitlines())
