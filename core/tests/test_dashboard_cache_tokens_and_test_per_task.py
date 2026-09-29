"""Issue #575: cache-token fields (D.3) and seed/sealed-test per-task visibility.

Both pieces are dashboard-reducer-side only:
  * `cache_read_tokens` / `cache_creation_tokens` are read from a step event (when an
    upstream capture puts them there — see #562, which owns run-optimizer's
    parse_cost) into per_iteration rows and a run-level total, kept SEPARATE from
    `tokens`/`opt_tokens` (folding them in would hide the cache hit rate they exist
    to explain).
  * `test_per_task` / `test_baseline_per_task` surface the sealed-test per-task
    rewards `finalize()` already persists on `final.json`'s `test`/`test_baseline`
    objects, previously read only for their aggregate reward.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _mk_run(tmp: Path, *, events, baseline=None, final=None):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    if baseline is not None:
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if final is not None:
        (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    return rd


_BASELINE = {"val": {"reward": 0.25, "cost_usd": 0.5, "seconds": 3.0, "tokens": 100,
                     "per_task": [{"task_id": "t1", "reward": 0.0, "feedback": ""},
                                  {"task_id": "t2", "reward": 0.5, "feedback": ""}]},
             "best_id": "seed"}


def _events():
    return [
        {"t": 0, "kind": "splits", "train": [1, 2], "val": [3, 4], "test": [5, 6], "seed": 0},
        {"t": 1, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "cost_usd": 0.5, "tokens": 100, "seconds": 3.0},
        {"t": 2, "kind": "baseline", "val": 0.25},
        {"t": 3, "kind": "evaluate", "split": "val", "tag": "cand_0001",
         "reward": 0.75, "cost_usd": 0.25, "tokens": 80, "seconds": 2.0},
        {"t": 4, "kind": "step", "candidate": "cand_0001", "accept": True,
         "reason": "accept", "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 9.0, "runner_seconds": 2.0, "cost_usd": 0.25,
         "tokens": 80, "opt_cost_usd": 1.25, "opt_tokens": 4000,
         "cache_read_tokens": 120000, "cache_creation_tokens": 3000},
        {"t": 5, "kind": "evaluate", "split": "test", "tag": "FINAL",
         "reward": 0.8, "cost_usd": 0.1, "tokens": 20, "seconds": 1.0},
        {"t": 6, "kind": "finalize", "test_reward": 0.8, "best_id": "cand_0001"},
    ]


_FINAL = {
    "test": {"reward": 0.8, "per_task": [{"task_id": "t1", "reward": 1.0, "feedback": ""},
                                          {"task_id": "t2", "reward": 0.6, "feedback": ""}]},
    "test_baseline": {"reward": 0.5, "per_task": [{"task_id": "t1", "reward": 0.0, "feedback": ""},
                                                   {"task_id": "t2", "reward": 1.0, "feedback": ""}]},
    "test_delta": 0.3,
    "best_id": "cand_0001",
}


def test_cache_tokens_surfaced_separately_from_opt_tokens():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_events(), baseline=_BASELINE, final=_FINAL)
        reduced = dashboard.reduce_run(rd)
        s = reduced["summary"]

        # Run-level totals: present, and NOT folded into `tokens`/`opt_tokens`.
        assert s["cache_read_tokens"] == 120000
        assert s["cache_creation_tokens"] == 3000

        row = next(r for r in s["per_iteration"] if r["candidate"] == "cand_0001")
        assert row["optimizer_tokens"] == 4000  # opt_tokens itself unchanged/not folded
        assert row["optimizer_cache_read_tokens"] == 120000
        assert row["optimizer_cache_creation_tokens"] == 3000


def test_cache_tokens_absent_means_not_recorded_not_zero():
    """A run with no cache fields on any event must report None, not 0 — the same
    "absent means not recorded" rule the rest of the ledger already follows."""
    from cap_evolve import dashboard
    events = _events()
    del events[4]["cache_read_tokens"]
    del events[4]["cache_creation_tokens"]
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, baseline=_BASELINE, final=_FINAL)
        s = dashboard.reduce_run(rd)["summary"]
        assert s["cache_read_tokens"] is None
        assert s["cache_creation_tokens"] is None
        row = next(r for r in s["per_iteration"] if r["candidate"] == "cand_0001")
        assert row["optimizer_cache_read_tokens"] is None
        assert row["optimizer_cache_creation_tokens"] is None


def test_sealed_test_per_task_visible_for_seed_and_best():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_events(), baseline=_BASELINE, final=_FINAL)
        s = dashboard.reduce_run(rd)["summary"]

        assert s["test_per_task"] == {"t1": 1.0, "t2": 0.6}
        assert s["test_baseline_per_task"] == {"t1": 0.0, "t2": 1.0}
        assert s["capabilities"]["test_per_task"] is True


def test_sealed_test_per_task_absent_when_final_has_none():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_events(), baseline=_BASELINE,
                     final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        s = dashboard.reduce_run(rd)["summary"]
        assert s["test_per_task"] is None
        assert s["test_baseline_per_task"] is None
        assert s["capabilities"]["test_per_task"] is False
