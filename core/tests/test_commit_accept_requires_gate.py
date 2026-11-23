"""#763: commit.py --decision accept needs a passing gate record, or --accept-without-gate."""

from __future__ import annotations

import copy
import json

import test_inconclusive_requires_growth as base


def _staged(tmp_path, verdict=None):
    run_dir, work = base._staged(tmp_path)
    t = copy.deepcopy(base.UNSTABLE_TABLE)
    if verdict is None:
        t["candidates"] = []
    else:
        t["candidates"][0]["verdict"] = verdict
    (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(t), encoding="utf-8")
    return run_dir, work


def _best(run_dir):
    from cap_evolve import RunDir
    return RunDir.open(run_dir.root).best_id


def _events(run_dir):
    return [json.loads(x) for x in run_dir.events_path.read_text().splitlines() if x.strip()]


def test_accept_without_gate_row_exits_2_and_keeps_best(tmp_path):
    run_dir, work = _staged(tmp_path)
    before = _best(run_dir)
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "no passing gate record" in p.stdout
    assert _best(run_dir) == before


def test_accept_with_passing_gate_row_accepts(tmp_path):
    run_dir, work = _staged(tmp_path, verdict="accept")
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr
    assert _best(run_dir) == "cand_2"


def test_accept_with_promote_gate_event_accepts(tmp_path):
    run_dir, work = _staged(tmp_path)
    run_dir.log_event("promote_gate", candidate="cand_2", verdict="accept")
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr


def test_accept_without_gate_escape_records_reason(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = base._commit(run_dir, work, "--accept-without-gate", "gate infra down", decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr
    assert _best(run_dir) == "cand_2"
    evs = [e for e in _events(run_dir) if e["kind"] == "accept_without_gate"]
    assert evs and evs[0]["reason"] == "gate infra down"
    acc = [e for e in _events(run_dir) if e["kind"] == "accept"]
    assert acc[-1]["accepted_without_gate"] == "gate infra down"
