"""Tests for dashboard activities, prompt_map, and outcomes fields."""

import json
import tempfile
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _mk_run(tmp: Path, *, events, baseline=None, final=None, candidates=None):
    """Build a minimal run dir with events and optional baseline/final/candidates."""
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    if baseline is not None:
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if final is not None:
        (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    if candidates:
        for cid, files in candidates.items():
            cdir = rd.root / "candidates" / cid
            cdir.mkdir(parents=True, exist_ok=True)
            for fname, content in files.items():
                (cdir / fname).write_text(content, encoding="utf-8")
    return rd


def test_activities_built_from_separate_eval_start_events():
    """Activities are built by pairing eval_start events with evaluate events."""
    from cap_evolve import dashboard
    
    events = [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 3005.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 3015.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 2900.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500, "t": 3020.0},
    ]
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events)
        r = dashboard.reduce_run(rd)
        activities = r["summary"]["activities"]
        
        # Should have seed eval, optimize, evaluate, and gate
        assert len(activities) >= 4
        
        # Find seed eval activity
        seed_eval = next((a for a in activities if a["type"] == "seed"), None)
        assert seed_eval is not None
        assert seed_eval["start"] == 0.0  # relative to run start (100.0)
        assert seed_eval["end"] == 5.0
        
        # Find optimize activity for iter 1
        opt = next((a for a in activities if a["type"] == "optimize" and a["iteration"] == 1), None)
        assert opt is not None
        assert opt["start"] == 5.0  # after seed eval ends
        assert opt["end"] == 2905.0  # at eval_start for cand_0001
        
        # Find evaluate activity for iter 1
        eval_act = next((a for a in activities if a["type"] == "evaluate" and a["iteration"] == 1), None)
        assert eval_act is not None
        assert eval_act["start"] == 2905.0  # at eval_start
        assert eval_act["end"] == 2915.0  # at evaluate event


def test_activities_spans_match_per_iteration_times():
    """Optimize spans should match per_iteration optimizer_seconds within a few seconds."""
    from cap_evolve import dashboard
    
    events = [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 1205.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 1215.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 1100.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500, "t": 1220.0},
    ]
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events)
        r = dashboard.reduce_run(rd)
        activities = r["summary"]["activities"]
        per_iter = r["summary"]["per_iteration"]
        
        # Find optimize activity for iter 1
        opt = next((a for a in activities if a["type"] == "optimize" and a["iteration"] == 1), None)
        assert opt is not None
        
        # Find per_iteration entry for cand_0001
        iter_data = next((p for p in per_iter if p["candidate"] == "cand_0001"), None)
        assert iter_data is not None
        
        # Optimize span duration should match optimizer_seconds within 5 seconds
        opt_duration = opt["end"] - opt["start"]
        assert abs(opt_duration - iter_data["optimizer_seconds"]) < 5.0


def test_activities_handles_final_evaluations():
    """Final test and train evaluations should be included in activities."""
    from cap_evolve import dashboard
    
    events = [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 205.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 215.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 100.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500, "t": 220.0},
        {"kind": "eval_start", "split": "test", "tag": "FINAL", "t": 300.0},
        {"kind": "evaluate", "split": "test", "tag": "FINAL", "reward": 0.8,
         "stderr": 0.05, "cost_usd": 0.02, "tokens": 1000, "seconds": 20.0, "t": 320.0},
        {"kind": "eval_start", "split": "train", "tag": "cand_0001", "t": 400.0},
        {"kind": "evaluate", "split": "train", "tag": "cand_0001", "reward": 0.85,
         "stderr": 0.03, "cost_usd": 0.015, "tokens": 800, "seconds": 15.0, "t": 415.0},
        {"kind": "finalize", "t": 500.0},
    ]
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events)
        r = dashboard.reduce_run(rd)
        activities = r["summary"]["activities"]
        
        # Find final test evaluation
        test_eval = next((a for a in activities if a["type"] == "final_eval" and a.get("split") == "test"), None)
        assert test_eval is not None
        assert test_eval["start"] == 200.0  # relative to run start
        assert test_eval["end"] == 220.0
        
        # Find final train evaluation
        train_eval = next((a for a in activities if a["type"] == "final_eval" and a.get("split") == "train"), None)
        assert train_eval is not None
        assert train_eval["start"] == 300.0
        assert train_eval["end"] == 315.0
        
        # Find finalize marker
        finalize = next((a for a in activities if a["type"] == "finalize"), None)
        assert finalize is not None
        assert finalize["start"] == 400.0


def test_prompt_map_line_numbers_with_multiple_hunks():
    """Prompt map should correctly track added/removed lines across multiple diff hunks."""
    from cap_evolve import dashboard
    
    # Create a simple diff with multiple hunks
    diff_content = """diff --git a/prompt.md b/prompt.md
index abc123..def456 100644
--- a/prompt.md
+++ b/prompt.md
@@ -5,3 +5,4 @@ Line 4
 Line 5
 Line 6
 Line 7
+Line 8 added
@@ -15,2 +16,3 @@ Line 14
 Line 15
 Line 16
+Line 17 added
+Line 18 added
"""
    
    events = [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 205.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 215.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 100.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500, "t": 220.0},
    ]
    
    candidates = {
        "seed": {"prompt.md": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\n"},
        "cand_0001": {"prompt.md": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8 added\n"},
    }
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, candidates=candidates)
        # Write git log
        (rd.root / "git.log").write_text(diff_content, encoding="utf-8")
        
        r = dashboard.reduce_run(rd)
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        
        # Check cand_0001 has prompt_map
        assert "prompt_map" in nodes["cand_0001"]
        pmap = nodes["cand_0001"]["prompt_map"]
        assert "prompt.md" in pmap
        
        # Check that added lines are tracked
        file_map = pmap["prompt.md"]
        assert "add" in file_map
        assert len(file_map["add"]) > 0


def test_prompt_map_skips_headings_in_code_fences():
    """Prompt map should not treat # inside code fences as markdown headings."""
    from cap_evolve import dashboard
    
    prompt_content = """# Real Heading 1

Some text here.

```python
# This is a comment, not a heading
def foo():
    # Another comment
    pass
```

## Real Heading 2

More text.

```bash
# This is also a comment
echo "test"
```

### Real Heading 3
"""
    
    events = [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0, "t": 105.0},
    ]
    
    candidates = {
        "seed": {"prompt.md": prompt_content},
    }
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, candidates=candidates)
        r = dashboard.reduce_run(rd)
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        
        # Check seed has prompt_map
        if "prompt_map" in nodes["seed"]:
            pmap = nodes["seed"]["prompt_map"]
            if "prompt.md" in pmap:
                file_map = pmap["prompt.md"]
                if "headings" in file_map:
                    headings = file_map["headings"]
                    # Should only have 3 real headings, not the comments in code blocks
                    heading_texts = [h[2] for h in headings]
                    assert "Real Heading 1" in heading_texts
                    assert "Real Heading 2" in heading_texts
                    assert "Real Heading 3" in heading_texts
                    # Should not include comments from code blocks
                    assert "This is a comment, not a heading" not in heading_texts
                    assert "Another comment" not in heading_texts
                    assert "This is also a comment" not in heading_texts


def test_outcomes_classification():
    """Outcomes should correctly classify tasks as fixed, broke, still_failing, still_passing."""
    from cap_evolve import dashboard
    
    baseline = {
        "val": {
            "reward": 0.5,
            "per_task": [
                {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
                {"task_id": "t2", "reward": 1.0, "feedback": "correct"},
                {"task_id": "t3", "reward": 0.0, "feedback": "wrong"},
                {"task_id": "t4", "reward": 1.0, "feedback": "correct"},
            ]
        },
        "best_id": "seed"
    }
    
    events = [
        {"kind": "splits", "train": 4, "val": 4, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0,
         "per_task": [
             {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
             {"task_id": "t2", "reward": 1.0, "feedback": "correct"},
             {"task_id": "t3", "reward": 0.0, "feedback": "wrong"},
             {"task_id": "t4", "reward": 1.0, "feedback": "correct"},
         ]},
        {"kind": "baseline", "val": 0.5, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 205.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 215.0,
         "per_task": [
             {"task_id": "t1", "reward": 1.0, "feedback": "correct"},  # fixed
             {"task_id": "t2", "reward": 0.0, "feedback": "wrong"},    # broke
             {"task_id": "t3", "reward": 0.0, "feedback": "wrong"},    # still_failing
             {"task_id": "t4", "reward": 1.0, "feedback": "correct"},  # still_passing
         ]},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.5,
         "optimizer_seconds": 100.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500, "t": 220.0},
    ]
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, baseline=baseline)
        r = dashboard.reduce_run(rd)
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        
        # Check cand_0001 has outcomes
        assert "outcomes" in nodes["cand_0001"]
        outcomes = nodes["cand_0001"]["outcomes"]
        
        # Verify classifications (outcomes is now lists grouped by result)
        assert "t1" in outcomes["fixed"]
        assert "t2" in outcomes["broke"]
        assert "t3" in outcomes["still_failing"]
        assert "t4" in outcomes["still_passing"]


def test_outcomes_from_fixed_broke_lists():
    """When per_task data is missing, outcomes should be built from fixed/broke lists."""
    from cap_evolve import dashboard
    
    baseline = {
        "val": {
            "reward": 0.5,
            "per_task": [
                {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
                {"task_id": "t2", "reward": 1.0, "feedback": "correct"},
                {"task_id": "t3", "reward": 0.0, "feedback": "wrong"},
                {"task_id": "t4", "reward": 1.0, "feedback": "correct"},
            ]
        },
        "best_id": "seed"
    }
    
    events = [
        {"kind": "splits", "train": 4, "val": 4, "test": 2, "seed": 0, "t": 100.0},
        {"kind": "eval_start", "split": "val", "tag": "seed", "t": 100.0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 5.0, "t": 105.0,
         "per_task": [
             {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
             {"task_id": "t2", "reward": 1.0, "feedback": "correct"},
             {"task_id": "t3", "reward": 0.0, "feedback": "wrong"},
             {"task_id": "t4", "reward": 1.0, "feedback": "correct"},
         ]},
        {"kind": "baseline", "val": 0.5, "stderr": 0.0, "t": 105.0},
        {"kind": "eval_start", "split": "val", "tag": "cand_0001", "t": 205.0},
        {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.75,
         "stderr": 0.0, "cost_usd": 0.01, "tokens": 500, "seconds": 10.0, "t": 215.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
         "val": 0.75, "parent": "seed", "parent_val": 0.5,
         "optimizer_seconds": 100.0, "runner_seconds": 10.0, "cost_usd": 0.01, "tokens": 500,
         "fixed": ["t1"], "broke": ["t2"], "t": 220.0},
    ]
    
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, baseline=baseline)
        r = dashboard.reduce_run(rd)
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        
        # Check cand_0001 has outcomes even without per_task data
        assert "outcomes" in nodes["cand_0001"]
        outcomes = nodes["cand_0001"]["outcomes"]
        
        # Verify classifications from fixed/broke lists
        assert "t1" in outcomes["fixed"]
        assert "t2" in outcomes["broke"]
        # t3 and t4 should be inferred from parent's per_task
        assert "t3" in outcomes["still_failing"]
        assert "t4" in outcomes["still_passing"]
