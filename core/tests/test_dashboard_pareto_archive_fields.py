"""issue #684 item 9: once `round.py --mode pareto` writes its own gate table (item 1/2,
owned elsewhere), its real shape — confirmed against that PR's actual output — puts the
candidate's non-reward objective values and ParetoArchive membership on the per-candidate
row as ``objective_values``/``objective_stderrs``/``pareto_archive``:

    {"tag": "cand_1", "reward": 1.0, "objective_values": {"cost": 0.0},
     "objective_stderrs": {"cost": 0.0},
     "pareto_archive": {"inserted": True,
                         "reason": "inserted (non-dominated, significant win on >=1 objective)",
                         "values": {"reward": 1.0, "cost": 0.0}, "capacity": 15, "size_after": 1}}

Nothing read this before: ``dashboard.py``'s existing ``gate_table`` lookup (added for
``verdict_stable``) only copied that one field. This proves the SAME lookup now also
carries the pareto-mode fields through onto the node, so the dashboard can show whether
and why a candidate joined the persistent cross-round archive — without round.py or
commit.py changing at all (both are owned by a different workstream of #684)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

PARETO_TABLE = {
    "parent": {"tag": "seed", "reward": 0.5, "n_tasks": 10},
    "objectives": [{"name": "reward", "direction": "maximize"},
                   {"name": "cost", "direction": "minimize"}],
    "candidates": [{
        "tag": "cand_1", "reward": 1.0, "verdict": "accept",
        "objective_values": {"cost": 0.0}, "objective_stderrs": {"cost": 0.0},
        "pareto_archive": {
            "inserted": True,
            "reason": "inserted (non-dominated, significant win on >=1 objective)",
            "values": {"reward": 1.0, "cost": 0.0}, "capacity": 15, "size_after": 1,
        },
    }],
}


def _staged(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=3, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    work = run_dir.root / "work" / "cand_1"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)
    (run_dir.root / "work" / "round_i0.json").write_text(
        json.dumps(PARETO_TABLE), encoding="utf-8")
    return run_dir, work


def test_pareto_archive_fields_are_carried_onto_the_node(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work), "--decision", "accept",
         "--val", "1.0", "--val-unverified", "fixture: val not under test", "--note", "test",
         "--missing-handover-justification", "fixture",
         "--missing-ranked-issues-justification", "fixture",
         "--missing-diagnosis-justification", "fixture"],
        capture_output=True, text=True,
        env={**__import__("os").environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    assert p.returncode == 0, p.stdout + p.stderr

    from cap_evolve import dashboard
    node = {n["id"]: n for n in dashboard.reduce_run(run_dir)["graph"]["nodes"]}["cand_1"]
    assert node["objective_values"] == {"cost": 0.0}
    assert node["objective_stderrs"] == {"cost": 0.0}
    assert node["pareto_archive"]["inserted"] is True
    assert "non-dominated" in node["pareto_archive"]["reason"]
    assert node["pareto_archive"]["values"] == {"reward": 1.0, "cost": 0.0}
