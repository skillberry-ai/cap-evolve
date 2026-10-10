"""issue #684 item 10: optimizer_seconds/optimizer_usd are always 0 across real agent-mode
runs because nothing forces the driving agent to pass --optimizer-seconds/--optimizer-usd —
SKILL.md just asked, never checked. commit.py now logs an ``optimizer_cost_warning`` when
real wall-clock time clearly passed since the previous decision but the new commit still
carries zero optimizer cost, and the dashboard surfaces it on the node."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _run_dir(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=10, stall=10))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    return run_dir


def _work(run_dir, tag):
    work = run_dir.root / "work" / tag
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.candidate_dir("seed"), work)
    return work


def _commit(run_dir, work, tag, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", tag, "--from-dir", str(work), "--decision", "reject",
         "--val", "0.4", "--val-unverified", "fixture: val not under test", "--note", "test",
         "--missing-handover-justification", "fixture: journal handover not under test",
         "--missing-ranked-issues-justification", "fixture: ranked issues not under test",
         "--missing-diagnosis-justification", "fixture: diagnosis not under test",
         *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})


def _backdate_last_decision(run_dir, seconds_ago):
    """Rewrite the LAST ``reject``-kind event's ``t`` so it looks ``seconds_ago`` in the
    past — simulates real optimizer thinking time having elapsed before the NEXT commit
    (``_wallclock_since_last_decision`` reads exactly this kind of event)."""
    lines = run_dir.events_path.read_text(encoding="utf-8").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        rec = json.loads(lines[i])
        if rec.get("kind") == "reject":
            rec["t"] = time.time() - seconds_ago
            lines[i] = json.dumps(rec)
            break
    run_dir.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _last_decision_event(run_dir):
    """The last ``reject``-kind event — ``record_iteration`` logs a further ``step`` event
    right after it, which is a different record and carries no ``optimizer_cost_warning``."""
    last = None
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("kind") == "reject":
            last = rec
    return last


def test_no_warning_on_the_first_ever_decision(tmp_path):
    run_dir = _run_dir(tmp_path)
    work = _work(run_dir, "cand_1")
    p = _commit(run_dir, work, "cand_1")
    assert p.returncode == 0, p.stdout + p.stderr
    assert _last_decision_event(run_dir)["optimizer_cost_warning"] is None


def test_warns_when_real_time_passed_with_zero_optimizer_cost(tmp_path):
    run_dir = _run_dir(tmp_path)
    p1 = _commit(run_dir, _work(run_dir, "cand_1"), "cand_1")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    _backdate_last_decision(run_dir, 300)

    p2 = _commit(run_dir, _work(run_dir, "cand_2"), "cand_2")
    assert p2.returncode == 0, p2.stdout + p2.stderr
    out = json.loads(p2.stdout)
    ev = _last_decision_event(run_dir)
    assert ev["optimizer_cost_warning"], "300s elapsed with optimizer_seconds=0 must warn"
    assert any("optimizer_seconds=0" in w for w in out["warnings"])

    from cap_evolve import dashboard
    n = {x["id"]: x for x in dashboard.reduce_run(run_dir)["graph"]["nodes"]}["cand_2"]
    assert n["optimizer_cost_warning"]


def test_no_warning_when_optimizer_seconds_is_passed(tmp_path):
    run_dir = _run_dir(tmp_path)
    p1 = _commit(run_dir, _work(run_dir, "cand_1"), "cand_1")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    _backdate_last_decision(run_dir, 300)

    p2 = _commit(run_dir, _work(run_dir, "cand_2"), "cand_2",
                 "--optimizer-seconds", "250")
    assert p2.returncode == 0, p2.stdout + p2.stderr
    assert _last_decision_event(run_dir)["optimizer_cost_warning"] is None


def test_no_warning_under_the_threshold(tmp_path):
    run_dir = _run_dir(tmp_path)
    p1 = _commit(run_dir, _work(run_dir, "cand_1"), "cand_1")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    # No backdating: the real elapsed time between these two subprocess calls is well
    # under the 120s threshold.
    p2 = _commit(run_dir, _work(run_dir, "cand_2"), "cand_2")
    assert p2.returncode == 0, p2.stdout + p2.stderr
    assert _last_decision_event(run_dir)["optimizer_cost_warning"] is None
