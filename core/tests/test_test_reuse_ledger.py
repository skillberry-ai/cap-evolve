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
    return json.loads((rd.root / "final.json").read_text()).get("test_reuse_count", 0)


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


def test_act_finalize_keeps_test_reuse_count(tmp_path, capsys, monkeypatch):
    """`act finalize` rewrites final.json after commit_test; the reuse count must survive."""
    import hashlib
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_digest_and_act_verbs import Sh, _act, _args, _run as _act_run

    rd, project, _, _ = _act_run(tmp_path)
    th = hashlib.sha256(json.dumps(sorted(map(str, rd.read_splits().test))).encode()).hexdigest()
    (rd.root.parent / "test_ledger.jsonl").write_text(
        json.dumps({"test_hash": th, "run": "run_other", "time": 0}) + "\n", encoding="utf-8")

    def fake_finalize(cmd):
        r = RunDir.open(rd.root)
        r.begin_test_attempt()
        payload = {"test": {"reward": 1.0}, "best_id": "cur"}
        (r.root / "final.json").write_text(json.dumps(payload), encoding="utf-8")
        r.commit_test()
        return 0, json.dumps(payload), ""

    _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)],
         Sh(**{"run.py": fake_finalize}))
    assert _count(rd) == 1


def test_empty_test_splits_are_not_flagged_as_reuse(tmp_path):
    from cap_evolve.splits import Splits
    runs = []
    for ts in ("e1", "e2"):
        rd = RunDir.create(tmp_path, ts=ts)
        rd.write_splits(Splits(train=["x"], val=["x"], test=[]))
        (rd.root / "final.json").write_text("{}", encoding="utf-8")
        rd.begin_test_attempt()
        rd.reserve_test()
        rd.commit_test()
        runs.append(rd)
    assert all(_events(r, "test_reuse") == [] for r in runs)
    assert _count(runs[1]) == 0
