"""issue #420 item 3: an inconclusive-booked candidate must trigger ``grow.py``.

Round 3 of run 33492876620 produced exactly the case ``grow.py`` was built for: a candidate
above zero, below the significance bar, verdict flipping depending on which byte-identical
control it was compared against. The agent booked it ``inconclusive`` and moved on — the
transcript shows it had already read ``grow.py --help``, so this was not a discovery gap, it
was optional, and optional tools that fix an exact recurring failure do not get used.

``commit.py`` now refuses ``--decision inconclusive`` unless a ``work/grow_<candidate>_r*.json``
table already exists for that candidate — i.e. ``grow.py`` has bought it at least one extra
round of trials — or the driver passes ``--force`` and says why.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

UNSTABLE_TABLE = {
    "parent": {"tag": "seed", "reward": 0.51, "stderr": 0.13, "n_tasks": 10},
    "gate_reference": {"tag": "ctl_null_i1", "mode": "control", "reward": 0.4966666666666667},
    "gated_against": {"tag": "ctl_null_i1", "mode": "control"},
    "null_delta_between_control_replicates": 0.0167,
    "evidence_bar": {"value": 0.0167, "basis": "gap between byte-identical control replicates"},
    "candidates": [{
        "tag": "cand_2", "reward": 0.54, "gate_delta": 0.0433,
        "gate_threshold": 0.0492, "verdict": "inconclusive",
        "verdict_by_reference": {"ctl_null_i1": "reject", "ctl_null_i1r1": "accept"},
        "verdict_stable": False, "regressions": [], "eval_rc": 0, "eval_error": None,
    }],
}


def _staged(tmp_path, cid="cand_2"):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=3, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    work = run_dir.root / "work" / cid
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)
    (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(UNSTABLE_TABLE),
                                                         encoding="utf-8")
    return run_dir, work


def _commit(run_dir, work, *extra, cid="cand_2", decision="inconclusive", val="0.54"):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", cid, "--from-dir", str(work),
         "--decision", decision, "--val", val, "--note", "test", *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})


def test_inconclusive_without_growth_is_refused(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = _commit(run_dir, work)
    assert p.returncode != 0, f"inconclusive was booked without a grow.py run: {p.stdout}"
    assert "grow.py" in p.stdout


def test_inconclusive_with_force_is_still_allowed(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = _commit(run_dir, work, "--force")
    assert p.returncode == 0, f"commit.py --force failed: {p.stdout}\n{p.stderr}"
    assert json.loads(p.stdout)["decision"] == "inconclusive"


def test_inconclusive_after_a_grow_table_exists_is_allowed(tmp_path):
    run_dir, work = _staged(tmp_path)
    work_dir = run_dir.root / "work"
    (work_dir / "grow_cand_2_r1.json").write_text(json.dumps({
        "grown": "cand_2", "growth_round": 1,
        "candidates": [{"tag": "cand_2", "reward": 0.55, "verdict": "inconclusive"}],
    }), encoding="utf-8")

    p = _commit(run_dir, work)
    assert p.returncode == 0, f"commit.py failed even though grow.py already ran: {p.stdout}"
    assert json.loads(p.stdout)["decision"] == "inconclusive"


def test_round_next_line_points_the_driver_at_grow_py():
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert "grow.py" in src, (
        "round.py's inconclusive reading no longer tells the driver to grow the candidate "
        "before booking it, so the fix is only enforced silently in commit.py")
