"""commit.py must refuse the `--reject-basis driver_judgement` escape hatch when a
candidate never had a screen.py record OR a full-val gate row — the exact bypass a real
run used to commit a candidate (`cand_1`) with zero screen/gate evidence on file for it.

`driver_judgement` is documented (SKILL.md, commit.py --help) as "the gate ACCEPTED and
you are overriding it for some other reason" — using it when NO gate ever ran, and the
candidate was never screened either, skips the whole screen-then-gate structure rather
than overriding a verdict that ran. This locks down that refusing it (unless
--bypassed-gate-justification is given) does not regress, and that the legitimate cases
(a screen record exists; a gate row exists) are untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
AGENT_SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
AGENT_COMMIT = AGENT_SCRIPTS / "commit.py"

sys.path.insert(0, str(CORE))


def _run_dir(tmp_path, ts):
    from cap_evolve import Budget, RunDir
    return RunDir.create(tmp_path / ".capevolve", ts=ts,
                         budget=Budget(max_iterations=10, max_metric_calls=400, stall=10))


def _commit(run_dir, candidate_id, from_dir, decision, val=None, extra=()):
    env = dict(os.environ, PYTHONPATH=str(CORE))
    cmd = [sys.executable, str(AGENT_COMMIT), "--run-dir", str(run_dir.root),
           "--candidate-id", candidate_id, "--from-dir", str(from_dir),
           "--decision", decision, "--note", f"{decision} via test",
           "--missing-handover-justification", "fixture: journal handover not under test"]
    if val is not None:
        cmd += ["--val", str(val)]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          cwd=str(AGENT_COMMIT.parent))


def _events(run_dir, kind=None):
    if not run_dir.events_path.is_file():
        return []
    evs = [json.loads(ln) for ln in
           run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return evs if kind is None else [e for e in evs if e.get("kind") == kind]


def _staged(tmp_path, ts):
    run_dir = _run_dir(tmp_path, ts)
    run_dir.set_best("seed")
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "policy.md").write_text("seed\n", encoding="utf-8")
    run_dir.snapshot("seed", seed_dir)
    work = tmp_path / "cand_1"
    work.mkdir()
    (work / "policy.md").write_text("v1\n", encoding="utf-8")
    return run_dir, work


def test_bare_driver_judgement_refused_with_no_screen_or_gate_history(tmp_path):
    run_dir, work = _staged(tmp_path, "byp1")
    out = _commit(run_dir, "cand_1", work, "reject",
                  extra=["--reject-basis", "driver_judgement"])
    assert out.returncode != 0, f"bypassed screen AND gate with no justification: {out.stdout}"
    assert "bypassed-gate-justification" in out.stdout
    # Refused BEFORE booking: no decision event, no snapshot promotion.
    assert not _events(run_dir, "reject")


def test_driver_judgement_proceeds_with_a_bypass_justification(tmp_path):
    run_dir, work = _staged(tmp_path, "byp2")
    out = _commit(run_dir, "cand_1", work, "reject",
                  extra=["--reject-basis", "driver_judgement",
                         "--bypassed-gate-justification",
                         "infra failure before any rollout could be scored"])
    assert out.returncode == 0, out.stdout + out.stderr
    payload = json.loads(out.stdout)
    assert payload["decision"] == "reject"
    assert any("screen+gate bypass" in w for w in payload["warnings"]), payload["warnings"]

    ev = _events(run_dir, "reject")[-1]
    assert ev["bypassed_screen_and_gate"] is True
    assert ev["bypassed_gate_justification"] == "infra failure before any rollout could be scored"


def test_driver_judgement_not_fooled_by_another_candidates_screen_record(tmp_path):
    """A screen record for a DIFFERENT candidate tag (fresh events.jsonl, no history at all
    for this tag) must not satisfy the guard — the glob has to be tag-specific, not just
    "some screen file exists in this run"."""
    run_dir, work = _staged(tmp_path, "byp4")
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_2__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    assert not run_dir.events_path.is_file()  # fresh run: no events.jsonl yet
    out = _commit(run_dir, "cand_1", work, "reject",
                  extra=["--reject-basis", "driver_judgement"])
    assert out.returncode != 0, (
        f"a screen record for cand_2 wrongly satisfied the guard for cand_1: {out.stdout}")
    assert "bypassed-gate-justification" in out.stdout


def test_driver_judgement_with_a_screen_record_needs_no_justification(tmp_path):
    """A candidate the screen ladder DID touch is not the bypass this guard targets —
    only the "skipped screen AND gate entirely" case requires the extra flag."""
    run_dir, work = _staged(tmp_path, "byp3")
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_1__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    out = _commit(run_dir, "cand_1", work, "reject",
                  extra=["--reject-basis", "driver_judgement"])
    assert out.returncode == 0, out.stdout + out.stderr
    payload = json.loads(out.stdout)
    assert not any("screen+gate bypass" in w for w in payload["warnings"])
