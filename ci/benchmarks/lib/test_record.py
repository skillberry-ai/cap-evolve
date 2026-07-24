import json
from pathlib import Path

import record  # same dir; run pytest from ci/benchmarks/lib

TASK_OK = {
    "bench": "tau2", "task": "35",
    "reward_baseline": 0.0, "reward_opt": 1.0, "reward_delta": 1.0, "flipped": True,
    "latency_baseline_s": 10.0, "latency_opt_s": 11.0,
    "cost_baseline_usd": 0.0, "cost_opt_runner_usd": 0.0,
    "optimizer_usd": 0.05, "optimizer_tokens": 0, "optimizer_seconds": 0, "iterations": 1,
}
TASK2 = {**TASK_OK, "task": "37", "reward_baseline": 0.0, "reward_opt": 0.0,
         "flipped": False, "optimizer_usd": 0.03}


def _write_jsonl(p: Path, rows):
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_rollup_math():
    r = record.rollup([TASK_OK, TASK2])
    assert r == {"reward_base": 0.0, "reward_opt": 0.5, "flips": 1, "n": 2, "optimizer_usd": 0.08}


def test_rollup_empty_is_none():
    assert record.rollup([]) is None


def test_build_success(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK, TASK2])
    meta = {"run_id": 1, "bench": "tau2", "conclusion": "success", "date": "2026-07-23T00:00:00Z"}
    rec = record.build_record(m, meta)
    assert rec["schema"] == 1
    assert rec["run_id"] == 1 and rec["bench"] == "tau2"
    assert len(rec["tasks"]) == 2
    assert rec["suite"]["flips"] == 1 and rec["suite"]["n"] == 2


def test_build_failed_run_has_null_suite(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK])
    meta = {"run_id": 2, "bench": "tau2", "conclusion": "failure", "date": "d"}
    rec = record.build_record(m, meta)
    assert rec["suite"] is None
    assert len(rec["tasks"]) == 1


def test_build_missing_metrics(tmp_path):
    meta = {"run_id": 3, "bench": "swebench", "conclusion": "success", "date": "d"}
    rec = record.build_record(tmp_path / "nope.jsonl", meta)
    assert rec["tasks"] == [] and rec["suite"] is None


def test_aggregate_sorts_and_counts(tmp_path):
    d = tmp_path / "records"; d.mkdir()
    (d / "1__tau2.json").write_text(json.dumps({"run_id": 1, "bench": "tau2", "date": "2026-07-20T00:00:00Z"}))
    (d / "2__tau2.json").write_text(json.dumps({"run_id": 2, "bench": "tau2", "date": "2026-07-22T00:00:00Z"}))
    recs, meta = record.aggregate(d, now="2026-07-23T09:00:00Z")
    assert [r["run_id"] for r in recs] == [2, 1]  # newest first
    assert meta == {"count": 2, "runs": 2, "updated": "2026-07-23T09:00:00Z"}


def test_build_preserves_tier(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK])
    rec = record.build_record(m, {"run_id": 9, "bench": "tau2", "tier": "smoke",
                                   "conclusion": "success", "date": "d"})
    assert rec["tier"] == "smoke"
    # tier absent -> not fabricated (the page defaults missing tier to "smoke" at render)
    rec2 = record.build_record(m, {"run_id": 9, "bench": "tau2",
                                    "conclusion": "success", "date": "d"})
    assert "tier" not in rec2
