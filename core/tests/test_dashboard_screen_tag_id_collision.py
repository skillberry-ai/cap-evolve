"""PR #507 review finding #2: a ``screen`` event whose ``screens/<tag>.json`` file is
missing (or carries no ``screen_tag`` field) made the reducer fall back to the
candidate's own tag as the screen's id. Any candidate that was cheap-screened and then
went to full val produced a screen row and a graph node sharing one id — a duplicate
key wherever both are listed together (the frontend's Tasks-matrix columns), and any
``.find(n => n.id === selectedId)``-style lookup always resolving to the first entry.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

_EVENTS = [
    {"t": 1.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
     "stderr": 0.25, "n_scored": 2},
    {"t": 3.0, "kind": "baseline", "val": 0.5, "stderr": 0.25, "n_scored": 2},
    # No matching screens/cand_a.json is written below — the file-lookup misses.
    {"t": 4.0, "kind": "screen", "tag": "cand_a", "tier": 1, "ids": ["t1", "t2"],
     "fired": 2, "decision": "promote", "mean_delta": 0.5, "se": 0.5, "n": 2,
     "inconclusive": False},
    {"t": 5.0, "kind": "evaluate", "split": "val", "tag": "cand_a", "reward": 0.54,
     "stderr": 0.2, "n_scored": 2},
    {"t": 6.0, "kind": "accept", "candidate": "cand_a", "val": 0.54,
     "note": "promoted after full val"},
    {"t": 7.0, "kind": "finalize", "test_reward": 0.54, "best_id": "cand_a"},
]
_BASELINE = {"val": {"reward": 0.5, "stderr": 0.25, "cost_usd": 0.0, "seconds": 0.0,
                     "per_task": [{"task_id": "t1", "reward": 1.0},
                                  {"task_id": "t2", "reward": 0.0}]}}
_FINAL = {"test": {}, "best_id": "cand_a", "baseline_id": "seed"}


def _reduce():
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text(
        "\n".join(json.dumps(e) for e in _EVENTS) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps(_BASELINE), encoding="utf-8")
    (rd.root / "final.json").write_text(json.dumps(_FINAL), encoding="utf-8")
    return dashboard.reduce_run(rd)


def test_screen_tag_stays_distinct_from_the_candidates_own_id_when_no_file_matches():
    reduced = _reduce()
    node_ids = {n["id"] for n in reduced["graph"]["nodes"]}
    screens = reduced["summary"]["algo_extra"]["screens"]
    assert screens[0]["candidate"] == "cand_a"
    screen_tag = screens[0]["screen_tag"]
    assert screen_tag != "cand_a"
    assert screen_tag not in node_ids
    assert "cand_a" in node_ids
