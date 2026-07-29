"""``reduce_run`` is memoized on events.jsonl mtime+size+inode and the git store's
stamp (issue #119).

The dashboard backend re-folds the whole event log on every request and every SSE
tick, so the reduction is memoized. A stale reduction served during a LIVE run would
be worse than no cache at all, so the invalidation cases are the ones that matter:
an append must re-fold; a same-second append (mtime unchanged at 1s resolution) must
still re-fold because the size moved; a same-size replace-via-rename must re-fold
because the inode moved; and a git commit must re-fold even though the harness logs
its event BEFORE committing, so the event log has not moved at all.

Also pinned here: the FIFO cap (the dashboard is long-lived) and the resolved cache
key (an absolute and a relative path to one run dir must share one entry).
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
    # A fresh dict rather than .clear() on the shared global, so monkeypatch restores
    # whatever the rest of the suite had instead of leaving it permanently emptied.
    monkeypatch.setattr(dashboard, "_REDUCE_CACHE", {})
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


def test_a_git_commit_with_no_new_event_invalidates(monkeypatch):
    """B1: the harness logs "step" then commits 33 lines LATER (harness.py:1323/:1356).

    So a commit lands with the event log untouched. Before the git stamp was folded
    into the key, ``git_log`` stayed stale for the rest of the iteration.
    """
    from cap_evolve.store import make_store
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        store = make_store({"kind": "git"}, rd.root)
        store.init()
        assert store.commit("iter 1: ACCEPT cand_0001")["ok"]
        before = dashboard.reduce_run(rd)
        assert len(before["summary"]["git_log"]) == 1
        ev_stamp = rd.events_path.stat()
        assert store.commit("iter 2: reject cand_0002")["ok"]
        # the whole point: the event log did NOT move
        assert rd.events_path.stat().st_mtime_ns == ev_stamp.st_mtime_ns
        assert rd.events_path.stat().st_size == ev_stamp.st_size
        after = dashboard.reduce_run(rd)
        assert len(calls) == 2, "a new commit must re-fold"
        assert len(after["summary"]["git_log"]) == 2, "git_log must show the new commit"


def test_cache_is_capped_and_evicts_oldest(monkeypatch):
    """B2: the dashboard is long-lived and list_runs installs one entry per run."""
    dashboard, _ = _spy(monkeypatch)
    monkeypatch.setattr(dashboard, "_REDUCE_MAX", 3)
    with tempfile.TemporaryDirectory() as d:
        roots = []
        for i in range(6):
            rd = _mk_run(Path(d) / f"r{i}")
            dashboard.reduce_run(rd)
            roots.append(str(Path(rd.root).resolve()))
        assert len(dashboard._REDUCE_CACHE) == 3, "cap must hold"
        # FIFO: the three newest survive, the three oldest are gone
        assert list(dashboard._REDUCE_CACHE) == roots[-3:]


def test_absolute_and_relative_paths_share_one_entry(monkeypatch):
    """B3: RunDir.open does not resolve, so the key must (rundir.py:201)."""
    from cap_evolve import RunDir
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d) / "base")
        abs_root = Path(rd.root).resolve()
        cwd = os.getcwd()
        try:
            os.chdir(abs_root.parent)
            a = dashboard.reduce_run(RunDir.open(abs_root))
            b = dashboard.reduce_run(RunDir.open(Path(abs_root.name)))
        finally:
            os.chdir(cwd)
        assert len(dashboard._REDUCE_CACHE) == 1, dict.keys(dashboard._REDUCE_CACHE)
        assert len(calls) == 1 and b is a


def test_truncating_the_event_log_invalidates(monkeypatch):
    """N7: shrink was untested; size moving down must invalidate like moving up."""
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        assert dashboard.reduce_run(rd)["summary"]["counts"]["total"] == 2
        lines = rd.events_path.read_text(encoding="utf-8").splitlines()[:2]
        rd.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        after = dashboard.reduce_run(rd)
        assert len(calls) == 2 and after["summary"]["counts"]["total"] == 1


def test_same_size_replace_via_rename_invalidates(monkeypatch):
    """N1: st_ino in the key catches a same-size rename-over at an identical mtime."""
    dashboard, calls = _spy(monkeypatch)
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        assert dashboard.reduce_run(rd)["summary"]["best_val"] == 0.75
        st = rd.events_path.stat()
        swapped = [dict(e) for e in _EVENTS]
        swapped[2]["val"] = 0.95  # same JSON byte length as 0.75
        tmp = rd.root / "events.new"
        tmp.write_text("\n".join(json.dumps(e) for e in swapped) + "\n", encoding="utf-8")
        assert tmp.stat().st_size == st.st_size, "probe must hold size constant"
        os.replace(tmp, rd.events_path)
        os.utime(rd.events_path, ns=(st.st_atime_ns, st.st_mtime_ns))
        assert rd.events_path.stat().st_mtime_ns == st.st_mtime_ns
        after = dashboard.reduce_run(rd)
        assert len(calls) == 2, "a new inode must invalidate at identical mtime+size"
        assert after["summary"]["best_val"] == 0.95


def test_mutating_a_returned_reduction_is_visible_to_the_next_caller():
    """N3 tripwire: the shared-object contract is read-only and NOT defended.

    This pins the documented behaviour so a future deepcopy-on-hit (which would eat
    the whole win) is a deliberate, test-breaking decision rather than an accident.
    """
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d))
        first = dashboard.reduce_run(rd)
        first["summary"]["best_val"] = "MUTATED"
        assert dashboard.reduce_run(rd)["summary"]["best_val"] == "MUTATED"
