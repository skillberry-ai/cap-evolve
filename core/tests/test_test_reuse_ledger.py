"""A test split scored by two run folders under one base is warned about (never refused)."""
import json

from cap_evolve.rundir import RunDir
from cap_evolve.splits import make_splits


def _finalize(base, ts, ids):
    rd = RunDir.create(base, ts=ts)
    rd.write_splits(make_splits(ids, seed=0))
    (rd.root / "final.json").write_text("{}", encoding="utf-8")
    rd.begin_test_attempt()
    rd.reserve_test()
    rd.commit_test()
    return rd


def _events(rd, kind):
    if not rd.events_path.is_file():
        return []
    return [r for r in map(json.loads, rd.events_path.read_text().splitlines()) if r["kind"] == kind]


def _count(rd):
    return json.loads((rd.root / "final.json").read_text())["test_reuse_count"]


def test_second_run_with_same_test_ids_is_warned(tmp_path):
    ids = [f"t{i}" for i in range(8)]
    a = _finalize(tmp_path, "a", ids)
    b = _finalize(tmp_path, "b", ids)
    assert _events(a, "test_reuse") == [] and _count(a) == 0
    ev = _events(b, "test_reuse")
    assert len(ev) == 1 and ev[0]["runs"] == ["run_a"] and ev[0]["count"] == 1
    assert _count(b) == 1


def test_different_test_ids_give_no_warning(tmp_path):
    _finalize(tmp_path, "a", [f"t{i}" for i in range(8)])
    b = _finalize(tmp_path, "b", [f"u{i}" for i in range(8)])
    assert _events(b, "test_reuse") == [] and _count(b) == 0
