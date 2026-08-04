"""Held-out runs published `reward_opt: null` for every task, so the page showed "—".

`metrics.suite_report` paired per-task baseline from `baseline.json` (the VAL split) against
optimized from `final.json` (the TEST split). That was correct while every tier was
no-holdout (train==val==test), which its docstring said out loud. #266 gave `full`/`pilot`
genuinely disjoint splits, after which no task id could match — so every `reward_opt` came
back null, `record.rollup` returned None for the whole suite (it requires both sides), and
the benchmarks page rendered "—" in the reward column for precisely the runs whose numbers
matter most. Confirmed on record `30708908659__pilot-spreadsheetbench.json`: 50/50 tasks
with `reward_baseline`, 0/50 with `reward_opt`, `suite: null`.

`final.json` always carries BOTH sides over the same sealed tasks (`test_baseline` = seed,
`test` = best), so the honest pairing was available all along.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
UTILS = REPO / "ci" / "benchmarks" / "utils"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _metrics():
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    return _load("_bench_metrics", LIB / "metrics.py")


def _pt(task_id, reward, errored=False):
    return {"task_id": task_id, "reward": reward, "raw": {"errored": errored}}


def _run_dir(tmp: Path, *, held_out: bool, best="cand_0001") -> Path:
    """A run dir shaped like a real one. held_out=True gives disjoint val/test ids."""
    rd = tmp / "run_suite"
    rd.mkdir(parents=True)
    # held_out: val and test are DISJOINT (as since #266). else: train==val==test.
    val_ids = ["v1", "v2", "v3"] if held_out else ["t1", "t2"]
    (rd / "baseline.json").write_text(json.dumps({
        "val": {"split": "val", "reward": 0.4, "stderr": 0.1,
                "per_task": [_pt(i, 0.4) for i in val_ids]},
        "best_id": "seed",
    }))
    (rd / "final.json").write_text(json.dumps({
        "test": {"split": "test", "reward": 0.75, "stderr": 0.1,
                 "per_task": [_pt("t1", 1.0), _pt("t2", 0.5)]},
        "best_id": best,
        "test_baseline": {"split": "test", "reward": 0.25, "stderr": 0.1,
                          "per_task": [_pt("t1", 0.5), _pt("t2", 0.0)]},
        "baseline_id": "seed",
        "test_delta": 0.5,
    }))
    (rd / "state.json").write_text(json.dumps({"best_id": best, "spent": {"iterations": 2}}))
    (rd / "events.jsonl").write_text("")
    return rd


# --- the fix -----------------------------------------------------------------------------


def test_held_out_run_pairs_seed_vs_best_on_the_same_sealed_tasks(tmp_path):
    m = _metrics()
    rd = _run_dir(tmp_path, held_out=True)
    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "full", "azure/gpt-5.5", 2, jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]

    assert {r["task"] for r in rows} == {"t1", "t2"}, "rows must be the SEALED test tasks"
    assert all(r["reward_opt"] is not None for r in rows), "this is the bug: opt was null"
    by = {r["task"]: r for r in rows}
    assert by["t1"]["reward_baseline"] == 0.5 and by["t1"]["reward_opt"] == 1.0
    assert by["t1"]["reward_delta"] == 0.5
    assert by["t2"]["reward_baseline"] == 0.0 and by["t2"]["reward_opt"] == 0.5


def test_the_suite_rollup_is_no_longer_none_for_a_held_out_run(tmp_path):
    """rollup() needs both sides; null opt made it return None, which is what blanked the page."""
    m = _metrics()
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    rec = _load("_bench_record", LIB / "record.py")

    rd = _run_dir(tmp_path, held_out=True)
    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "full", "azure/gpt-5.5", 2, jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]

    suite = rec.rollup(rows, [])
    assert suite is not None, "the page renders '—' when this is None"
    assert suite["reward_base"] == 0.25 and suite["reward_opt"] == 0.75
    assert suite["n"] == 2


def test_no_holdout_run_keeps_its_train_fit_pairing(tmp_path):
    """smoke has train==val==test; its behaviour must not change."""
    m = _metrics()
    rd = _run_dir(tmp_path, held_out=False)
    jsonl = tmp_path / "metrics.jsonl"
    md = m.suite_report(str(rd), "spreadsheetbench", "smoke", "aws/gpt-oss-120b", 3,
                        jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]
    assert all(r["reward_opt"] is not None for r in rows)
    assert "train-fit" in md and "train==val==test" in md


def test_report_stops_claiming_no_holdout_on_a_held_out_run(tmp_path):
    """The old header asserted `train==val==test` unconditionally — false, and the exact
    claim a reader would rely on when judging whether a number generalizes."""
    m = _metrics()
    md = m.suite_report(str(_run_dir(tmp_path, held_out=True)), "spreadsheetbench", "full",
                        "azure/gpt-5.5", 2)
    assert "train==val==test" not in md
    assert "SEALED test tasks" in md and "held-out" in md
    # The headline must compare seed-on-test vs best-on-test, not val vs test.
    assert "0.250 → 0.750" in md


def test_best_equals_seed_yields_a_zero_delta_not_trial_noise(tmp_path):
    """When nothing was accepted, final.json's test_baseline IS the test result, so base==opt.
    The old val-vs-test pairing reported a spurious non-zero delta from re-scoring noise."""
    m = _metrics()
    rd = _run_dir(tmp_path, held_out=True, best="seed")
    same = {"split": "test", "reward": 0.75, "stderr": 0.1,
            "per_task": [_pt("t1", 1.0), _pt("t2", 0.5)]}
    f = json.loads((rd / "final.json").read_text())
    f["test_baseline"], f["baseline_id"], f["test_delta"] = same, "seed", 0.0
    (rd / "final.json").write_text(json.dumps(f))

    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "full", "azure/gpt-5.5", 2, jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]
    assert all(r["reward_delta"] == 0.0 for r in rows)


def test_infra_errored_side_still_suppresses_the_delta(tmp_path):
    m = _metrics()
    rd = _run_dir(tmp_path, held_out=True)
    f = json.loads((rd / "final.json").read_text())
    f["test"]["per_task"] = [_pt("t1", 0.0, errored=True), _pt("t2", 0.5)]
    (rd / "final.json").write_text(json.dumps(f))
    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "full", "azure/gpt-5.5", 2, jsonl_path=str(jsonl))
    rows = {json.loads(l)["task"]: json.loads(l) for l in jsonl.read_text().splitlines()}
    assert rows["t1"]["opt_infra"] is True and rows["t1"]["reward_delta"] is None
    assert rows["t2"]["reward_delta"] == 0.5


# --- the backfill utility ----------------------------------------------------------------


def test_rebuild_record_repairs_a_stale_record(tmp_path):
    """Records already published cannot be re-run; they are repaired from the artifact."""
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    stale = {
        "bench": "spreadsheetbench", "tier": "full", "conclusion": "success",
        "steps": [{"eval_usd": 1.0, "optimizer_usd": 2.0, "eval_seconds": 10, "optimizer_seconds": 20}],
        "tasks": [{"bench": "spreadsheetbench", "tier": "full", "task": "v1",
                   "reward_baseline": 0.4, "reward_opt": None, "reward_delta": None,
                   "opt_infra": False, "run_dir": "/x"}],
        "suite": None,
    }
    final = {
        "test": {"reward": 0.75, "per_task": [_pt("t1", 1.0), _pt("t2", 0.5)]},
        "test_baseline": {"reward": 0.25, "per_task": [_pt("t1", 0.5), _pt("t2", 0.0)]},
    }
    tasks = rb.rebuild_tasks(stale, final)
    assert [t["task"] for t in tasks] == ["t1", "t2"]
    assert all(t["reward_opt"] is not None for t in tasks)
    assert tasks[0]["reward_delta"] == 0.5
    assert all(t["tier"] == "full" and t["bench"] == "spreadsheetbench" for t in tasks)


def test_rebuild_record_leaves_an_already_correct_record_alone(tmp_path):
    """A record whose rows already carry an opt reward is not broken — never rewrite it, so
    the utility is safe to point at every record in the directory."""
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    original = [{"task": "t1", "reward_baseline": 0.4, "reward_opt": 0.6}]
    stale = {"bench": "b", "tier": "smoke", "tasks": original, "suite": None}
    final = {"test": {"per_task": [_pt("t1", 1.0)]},
             "test_baseline": {"per_task": [_pt("t1", 0.5)]}}
    assert rb.rebuild_tasks(stale, final) == original


def test_rebuild_record_skips_when_sides_cover_different_tasks(tmp_path):
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    original = [{"task": "v1", "reward_baseline": 0.4, "reward_opt": None}]
    stale = {"bench": "b", "tier": "full", "tasks": original, "suite": None}
    final = {"test": {"per_task": [_pt("t1", 1.0)]},
             "test_baseline": {"per_task": [_pt("OTHER", 0.5)]}}
    assert rb.rebuild_tasks(stale, final) == original


def test_rebuild_accepts_the_runs_real_final_json(tmp_path):
    """The artifact's UI snapshot is size-capped and truncates on a large test split — the
    639-task full tier does not fit — so the run's own final.json must be a valid source."""
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    fj = tmp_path / "final.json"
    fj.write_text(json.dumps({
        "test": {"reward": 0.75, "per_task": [_pt("t1", 1.0), _pt("t2", 0.5)]},
        "test_baseline": {"reward": 0.25, "per_task": [_pt("t1", 0.5), _pt("t2", 0.0)]},
    }), encoding="utf-8")
    assert rb._load_final(fj)["test"]["reward"] == 0.75


def test_a_truncated_artifact_snapshot_says_what_to_do_instead(tmp_path):
    """Failing with 'is truncated' and no remedy is how this wasted a cycle the first time."""
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    art = tmp_path / "art" / "ui" / "data"
    art.mkdir(parents=True)
    (art / "runs_run_suite_file_path_final_json.json").write_text(
        json.dumps({"truncated": True, "text": "{}"}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        rb._load_final(tmp_path / "art")
    assert "final.json" in str(e.value) and "truncated" in str(e.value)


def test_rebuild_is_idempotent(tmp_path):
    rb = _load("_rebuild_record", UTILS / "rebuild_record.py")
    stale = {"bench": "b", "tier": "full", "tasks": [{"run_dir": "/x"}], "suite": None}
    final = {"test": {"per_task": [_pt("t1", 1.0)]},
             "test_baseline": {"per_task": [_pt("t1", 0.5)]}}
    once = rb.rebuild_tasks(stale, final)
    twice = rb.rebuild_tasks({**stale, "tasks": once}, final)
    assert once == twice
