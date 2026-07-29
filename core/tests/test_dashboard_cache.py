"""``reduce_run`` is memoized on events.jsonl mtime+size (issue #119).

The dashboard backend re-folds the whole event log on every request and every SSE
tick, so the reduction is memoized. A stale reduction served during a LIVE run would
be worse than no cache at all, so the invalidation cases are the ones that matter:
an append must re-fold, and a same-second append (mtime unchanged at 1s resolution)
must still re-fold because the size moved.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

_EVENTS = [
    {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"kind": "baseline", "val": 0.25, "stderr": 0.0},
    {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
     "val": 0.75, "parent": "seed", "parent_val": 0.25},
]
_BASELINE = {"val": {"reward": 0.25, "per_task": [
    {"task_id": "t1", "reward": 0.0}, {"task_id": "t2", "reward": 0.5}]}, "best_id": "seed"}


def _mk_run(tmp: Path, events=_EVENTS):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n",
                              encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps(_BASELINE), encoding="utf-8")
    return rd


def _spy(monkeypatch):
    """Count real folds by wrapping the uncached reducer."""
    from cap_evolve import dashboard
    dashboard._REDUCE_CACHE.clear()
    calls = []
    real = dashboard._reduce_run_uncached

    def counting(run_dir):
        calls.append(1)
        return real(run_dir)

    monkeypatch.setattr(dashboard, "_reduce_run_uncached", counting)
    return dashboard, calls


def test_unchanged_event_log_hits_the_cache(monkeypatch):
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        first = dashboard.reduce_run(rd)
        second = dashboard.reduce_run(rd)
        assert len(calls) == 1, f"expected one fold, got {len(calls)}"
        assert second is first  # served from cache, not re-derived
        assert first["summary"]["best_val"] == 0.75


def test_appending_an_event_invalidates_the_cache(monkeypatch):
    """The critical case: a live run appends, the next read must NOT be stale."""
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        before = dashboard.reduce_run(rd)
        assert before["summary"]["counts"]["total"] == 2  # seed + cand_0001
        with rd.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "step", "candidate": "cand_0002",
                                 "accept": True, "reason": "up", "val": 0.9,
                                 "parent": "cand_0001", "parent_val": 0.75}) + "\n")
        after = dashboard.reduce_run(rd)
        assert len(calls) == 2, "append must re-fold"
        assert after["summary"]["counts"]["total"] == 3
        assert after["summary"]["best_val"] == 0.9  # fresh, not the cached 0.75


def test_same_mtime_append_still_invalidates(monkeypatch):
    """mtime alone is not enough: force the mtime back, size must still bust the key."""
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        dashboard.reduce_run(rd)
        st = rd.events_path.stat()
        with rd.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "step", "candidate": "cand_0002",
                                 "accept": True, "reason": "up", "val": 0.9,
                                 "parent": "cand_0001"}) + "\n")
        # Pretend the append happened within one mtime tick of the cached read.
        os.utime(rd.events_path, ns=(st.st_atime_ns, st.st_mtime_ns))
        assert rd.events_path.stat().st_mtime_ns == st.st_mtime_ns
        after = dashboard.reduce_run(rd)
        assert len(calls) == 2, "size change must invalidate even at identical mtime"
        assert after["summary"]["best_val"] == 0.9


def test_two_runs_do_not_share_a_cache_entry(monkeypatch):
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        a = _mk_run(Path(d1))
        b = _mk_run(Path(d2), events=_EVENTS + [
            {"kind": "step", "candidate": "cand_0002", "accept": True,
             "reason": "up", "val": 0.95, "parent": "cand_0001"}])
        ra, rb = dashboard.reduce_run(a), dashboard.reduce_run(b)
        assert len(calls) == 2
        assert ra["summary"]["best_val"] == 0.75
        assert rb["summary"]["best_val"] == 0.95
        # and each still hits its own entry
        assert dashboard.reduce_run(a) is ra and dashboard.reduce_run(b) is rb
        assert len(calls) == 2


def test_repeat_reduce_reuses_the_same_object_behavioral():
    """No internals: on an unchanged log the second reduce returns the SAME object.

    Fails on the pre-#119 reducer (each call built a fresh structure) and is the
    property the dashboard's per-request / per-SSE-tick path actually relies on.
    """
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        assert dashboard.reduce_run(rd) is dashboard.reduce_run(rd)


def test_reduce_after_append_reflects_the_new_event_behavioral():
    """No internals: appending must be visible on the very next reduce."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        assert dashboard.reduce_run(rd)["summary"]["best_val"] == 0.75
        with rd.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "step", "candidate": "cand_0002",
                                 "accept": True, "reason": "up", "val": 0.9,
                                 "parent": "cand_0001"}) + "\n")
        r = dashboard.reduce_run(rd)
        assert r["summary"]["best_val"] == 0.9
        assert r["summary"]["counts"]["total"] == 3


def test_missing_event_log_is_never_cached(monkeypatch):
    """No events.jsonl → no stable stamp → always re-fold (correct over fast)."""
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        rd.events_path.unlink()
        dashboard.reduce_run(rd)
        dashboard.reduce_run(rd)
        assert len(calls) == 2
