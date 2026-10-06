"""PR #507 review finding #1: ``commit.py --decision inconclusive`` logs an
``inconclusive`` event carrying ``gate_verdict``/``overrode_gate``/``reject_basis``,
followed by ``harness.record_iteration``'s own ``step`` event for the same candidate
(which carries none of those fields). ``_STEP_KINDS`` did not include ``inconclusive``,
so the reducer skipped that event outright and the audit-trail fields never reached the
node — they only ever showed up for accept/reject/provisional.
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
    {"t": 4.0, "kind": "evaluate", "split": "val", "tag": "cand_a", "reward": 0.54,
     "stderr": 0.2, "n_scored": 2},
    # commit.py's decision event: carries the audit trail.
    {"t": 5.0, "kind": "inconclusive", "candidate": "cand_a", "val": 0.54,
     "gate_verdict": "inconclusive", "overrode_gate": False, "reject_basis": None,
     "note": "indecisive (gate): verdict flips across control replicates"},
    # harness.record_iteration's own step event for the SAME candidate: no audit fields.
    {"t": 6.0, "kind": "step", "candidate": "cand_a", "accept": False, "val": 0.54,
     "parent": "seed", "reason": "indecisive (gate): verdict flips across control replicates"},
    {"t": 7.0, "kind": "finalize", "test_reward": 0.5, "best_id": "seed"},
]

_BASELINE = {"val": {"reward": 0.5, "stderr": 0.25, "cost_usd": 0.0, "seconds": 0.0,
                     "per_task": [{"task_id": "t1", "reward": 1.0},
                                  {"task_id": "t2", "reward": 0.0}]}}
_FINAL = {"test": {}, "best_id": "seed", "baseline_id": "seed"}


def _reduce():
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text(
        "\n".join(json.dumps(e) for e in _EVENTS) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps(_BASELINE), encoding="utf-8")
    (rd.root / "final.json").write_text(json.dumps(_FINAL), encoding="utf-8")
    return dashboard.reduce_run(rd)


def test_inconclusive_candidate_keeps_its_audit_fields():
    reduced = _reduce()
    node = next(n for n in reduced["graph"]["nodes"] if n["id"] == "cand_a")
    assert node["gate_verdict"] == "inconclusive"
    assert node["overrode_gate"] is False


def test_inconclusive_candidate_is_neither_accepted_nor_rejected():
    reduced = _reduce()
    node = next(n for n in reduced["graph"]["nodes"] if n["id"] == "cand_a")
    assert node["status"] == "indecisive"
