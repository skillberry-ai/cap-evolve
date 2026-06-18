import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import capevolve_dashboard  # noqa: E402,F401  (bootstraps cap_evolve onto path)


@pytest.fixture
def tmp_base(tmp_path):
    """An empty base dir that will hold run_* dirs."""
    return tmp_path


@pytest.fixture
def make_run(tmp_base):
    """Create a synthetic run dir under tmp_base; return its RunDir."""
    from cap_evolve import Budget, RunDir

    def _make(run_id="run_t", *, events, baseline=None, final=None):
        ts = run_id[len("run_"):] if run_id.startswith("run_") else run_id
        rd = RunDir.create(tmp_base, ts=ts, budget=Budget())
        rd.events_path.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
        if baseline is not None:
            (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        if final is not None:
            (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
        return rd

    return _make


# Shared minimal event stream: baseline + one accepted + one rejected candidate.
BASE_EVENTS = [
    {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
     "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 0.0},
    {"kind": "baseline", "val": 0.25, "stderr": 0.0},
    {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
     "val": 0.75, "parent": "seed", "parent_val": 0.25,
     "optimizer_seconds": 1.2, "runner_seconds": 0.5, "cost_usd": 0.01, "tokens": 500},
    {"kind": "step", "candidate": "cand_0002", "accept": False, "reason": "down",
     "val": 0.6, "parent": "cand_0001", "parent_val": 0.75,
     "optimizer_seconds": 1.0, "runner_seconds": 0.4, "cost_usd": 0.008, "tokens": 400},
]
