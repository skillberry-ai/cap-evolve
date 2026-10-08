"""detect_loop_patterns.py — pattern-detection correctness (#684 item 7).

Synthetic rollout fixtures only: a clear repeated-call pattern must be detected with the
right tool/count/tasks, no repeated pattern must yield an empty result, and a run one call
short of the minimum N must not be flagged.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
SCRIPT = SCRIPT_DIR / "detect_loop_patterns.py"


def _load():
    spec = importlib.util.spec_from_file_location("_detect_loop_patterns", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_DIR))
    spec.loader.exec_module(mod)
    return mod


def _rec(task_id, tool_calls):
    return {"rollout": {"task_id": task_id, "tool_calls": [{"name": n} for n in tool_calls]},
            "score": {"task_id": task_id}, "__file": f"{task_id}.json"}


def test_a_clear_repeated_call_run_is_detected_with_tool_count_and_task():
    m = _load()
    recs = [_rec("t1", ["get_reservation_details"] * 5 + ["cancel_reservation"])]
    patterns = m.find_loops(recs, min_n=3)
    assert patterns == [{"tool": "get_reservation_details", "repeat_count": 5,
                          "task_id": "t1", "file": "t1.json"}]
    by_tool = m.summarize(patterns)
    assert by_tool == {"get_reservation_details":
                        {"tasks": ["t1"], "max_repeat_count": 5, "occurrences": 1}}


def test_no_repeated_pattern_yields_empty_result():
    m = _load()
    recs = [_rec("t1", ["search_flights", "get_user", "book_flight"])]
    assert m.find_loops(recs, min_n=3) == []
    assert m.summarize([]) == {}


def test_a_run_one_short_of_the_minimum_is_not_flagged():
    m = _load()
    # exactly min_n - 1 repeats of the same tool, surrounded by different calls
    recs = [_rec("t1", ["get_user"] + ["get_reservation_details"] * 2 + ["cancel_reservation"])]
    assert m.find_loops(recs, min_n=3) == []


def test_calls_carried_in_trace_messages_are_also_scanned():
    m = _load()
    rec = {"rollout": {"task_id": "t2", "trace": [
        {"role": "assistant", "tool_calls": [{"function": {"name": "get_record"}}]},
        {"role": "assistant", "tool_calls": [{"function": {"name": "get_record"}}]},
        {"role": "assistant", "tool_calls": [{"function": {"name": "get_record"}}]},
    ]}, "score": {"task_id": "t2"}, "__file": "t2.json"}
    patterns = m.find_loops([rec], min_n=3)
    assert len(patterns) == 1 and patterns[0]["tool"] == "get_record" and patterns[0]["repeat_count"] == 3


def test_cli_scans_rollouts_on_disk_for_one_candidate_and_split(tmp_path):
    """End-to-end: real files under rollouts/val/, found via run_dir + tag + split."""
    (tmp_path / "state.json").write_text(
        json.dumps({"best_id": None, "budget": {}, "spent": {}}), encoding="utf-8")
    rollouts_dir = tmp_path / "rollouts" / "val"
    rollouts_dir.mkdir(parents=True)
    for i in range(2):
        rec = _rec(f"task{i}", ["get_reservation_details"] * 4 + ["cancel_reservation"])
        del rec["__file"]
        (rollouts_dir / f"task{i}__cand_1__t0.json").write_text(json.dumps(rec), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-dir", str(tmp_path), "--tag", "cand_1",
         "--split", "val", "--min-n", "3"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["n_rollouts_scanned"] == 2
    assert data["by_tool"]["get_reservation_details"]["occurrences"] == 2
    assert sorted(data["by_tool"]["get_reservation_details"]["tasks"]) == ["task0", "task1"]
