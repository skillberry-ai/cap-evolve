"""A kept run re-scored under another reward gives the baseline that reward would have measured.

The as-saved reward is the spreadsheetbench default, but the kept no-skill run was graded after
formula recalculation. Reusing its baseline unchanged would gate every new candidate against a
number in a different metric, so `rescore_run.py` re-reads each rollout's recorded metric and
rebuilds baseline.json and the seed's test result from them.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "ci" / "benchmarks" / "spreadsheetbench" / "utils" / "rescore_run.py"
sys.path.insert(0, str(REPO / "core"))


def _load():
    spec = importlib.util.spec_from_file_location("_rescore_run", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rollout(tid, recalc, as_saved, *, error=None):
    metrics = [
        {"name": "hard_restriction", "value": recalc, "primary": True, "direction": "higher"},
        {"name": "hard_no_recalc", "value": as_saved, "primary": False, "direction": "higher"},
    ]
    fb = f"{int(recalc)}/1 test cases passed (Cell-Level Manipulation, checked range: A1)."
    if recalc:
        fb += " All checks passed."
    return {"input": {}, "rollout": {"task_id": tid, "error": error},
            "score": {"task_id": tid, "reward": recalc, "feedback": fb,
                      "raw": {"test_case_results": [int(recalc)],
                              "test_case_results_no_recalc": [int(as_saved)]},
                      "metrics": metrics}}


def _run_dir(tmp: Path) -> Path:
    rd = tmp / "run_suite"
    for split, tag, rows in (
        ("val", "seed", [("v1", 1.0, 1.0), ("v2", 1.0, 0.0)]),
        ("train", "seed", [("r1", 1.0, 0.0), ("r2", 0.0, 0.0)]),
        ("test", "FINAL", [("t1", 1.0, 1.0), ("t2", 1.0, 0.0), ("t3", 1.0, 1.0), ("t4", 0.0, 0.0)]),
    ):
        d = rd / "rollouts" / split
        d.mkdir(parents=True)
        for tid, rc, nr in rows:
            (d / f"{tid}__{tag}__t0.json").write_text(json.dumps(_rollout(tid, rc, nr)))
    (rd / "splits.json").write_text(json.dumps({"train": ["r1", "r2"], "val": ["v1", "v2"],
                                                "test": ["t1", "t2", "t3", "t4"], "seed": 0,
                                                "test_used": True}))
    (rd / "baseline.json").write_text(json.dumps({"val": {"reward": 1.0}, "train": {"reward": 0.5},
                                                 "best_id": "seed"}))
    (rd / "final.json").write_text(json.dumps({"best_id": "seed", "baseline_id": "seed",
                                              "test": {"reward": 0.75}, "test_baseline": {"reward": 0.75},
                                              "seed": {"test": {"reward": 0.75}}}))
    (rd / "state.json").write_text(json.dumps({"best_id": "seed", "spent": {}}))
    (rd / "events.jsonl").write_text("")
    return rd


def test_the_baseline_and_seed_test_are_rebuilt_in_the_new_metric(tmp_path):
    rd = _run_dir(tmp_path)
    out = _load().rescore(rd, "hard_no_recalc")
    assert out == {"val": 0.5, "train": 0.0, "test": 0.5}
    base = json.loads((rd / "baseline.json").read_text())
    assert base["val"]["reward"] == 0.5 and base["train"]["reward"] == 0.0
    final = json.loads((rd / "final.json").read_text())
    for key in ("test", "test_baseline"):
        assert final[key]["reward"] == 0.5
    assert final["seed"]["test"]["reward"] == 0.5


def test_each_rollout_says_why_a_formula_answer_now_fails(tmp_path):
    rd = _run_dir(tmp_path)
    _load().rescore(rd, "hard_no_recalc")
    rec = json.loads((rd / "rollouts" / "val" / "v2__seed__t0.json").read_text())
    assert rec["score"]["reward"] == 0.0
    assert [m["name"] for m in rec["score"]["metrics"] if m["primary"]] == ["hard_no_recalc"]
    fb = rec["score"]["feedback"]
    assert fb.startswith("0/1 test cases passed") and "FORMULAS" in fb and "All checks passed" not in fb


def test_rescoring_back_to_recalc_restores_the_original_numbers(tmp_path):
    rd = _run_dir(tmp_path)
    mod = _load()
    mod.rescore(rd, "hard_no_recalc")
    assert mod.rescore(rd, "hard_restriction") == {"val": 1.0, "train": 0.5, "test": 0.75}


def test_run_suite_reuses_a_rescored_copy_never_the_kept_slot():
    sh = (REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh").read_text(encoding="utf-8")
    block = sh.split("# REUSE THE LATEST RUN'S SEED", 1)[1].split('cat > "$PROJ/capevolve.yaml"', 1)[0]
    assert "rescore_run.py" in block and '--metric "$SB_REWARD_METRIC"' in block
    assert 'REUSE_YAML="reuse_baseline:     \\"$RESCORED/run_suite\\""' in block


def _pt(tid, recalc, as_saved):
    return {"task_id": tid, "reward": recalc, "n": 1, "raw": {},
            "metrics": [{"name": "hard_restriction", "value": recalc, "primary": True, "direction": "higher"},
                        {"name": "hard_no_recalc", "value": as_saved, "primary": False, "direction": "higher"}]}


def test_a_seed_test_score_that_was_itself_reused_is_rescored_from_the_stored_result(tmp_path):
    """The kept run may be an optimization run whose seed test score was REUSED: it has champion
    FINAL rollouts but no FINAL_seed ones. Rebuilding from rollouts alone gave an empty result and
    a seed test score of 0.0 (run 36522466236)."""
    rd = _run_dir(tmp_path)
    stored = {"split": "test", "reward": 0.75,
              "per_task": [_pt("t1", 1.0, 1.0), _pt("t2", 1.0, 0.0), _pt("t3", 1.0, 1.0), _pt("t4", 0.0, 0.0)]}
    (rd / "final.json").write_text(json.dumps({"best_id": "cand_0003", "baseline_id": "seed",
                                              "test": {"reward": 0.9}, "test_baseline": stored,
                                              "seed": {"test": stored}}))
    out = _load().rescore(rd, "hard_no_recalc")
    assert out["test"] == 0.5
    final = json.loads((rd / "final.json").read_text())
    assert final["seed"]["test"]["reward"] == 0.5 and final["test_baseline"]["reward"] == 0.5
    assert final["test"]["reward"] == 0.9, "the champion's own test result must be left alone"
