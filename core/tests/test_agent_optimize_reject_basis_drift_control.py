"""commit.py's ``--reject-basis gate`` refusal only ever checked the RAW parent-relative gate
verdict, so a driver whose ROUND-level ``control_relative`` comparison (drift-corrected: the
same round's byte-identical null-control replicate, not the stored parent reward) said reject
while the raw gate said accept had no structured basis to book that reject with. It had to
fall back to ``driver_judgement`` and hand-write the disagreement into ``--note`` — confirmed
live: exactly this situation forced that fallback for a common, nameable case.

``--reject-basis drift_control`` is the fix: a new, distinct basis (not a loosening of
``gate``'s existing meaning, which specifically asserts the RAW gate rejected) for exactly this
disagreement, validated against ``round.py``'s ``control_relative``/``verdict_stable`` fields on
the same table ``commit.py`` already reads for ``gate``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from test_agent_optimize_round_attribution import (
    REPO, ROUND_TABLE, SCRIPTS, _run_dir_with_round_table,
)


def _commit_with_basis(run_dir, work, basis: str):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work),
         "--decision", "reject", "--val", "0.5333333333333333",
         "--reject-basis", basis,
         "--note", "the drift-controlled comparison disagreed with the raw parent-relative one"],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    return p


def test_reject_basis_gate_still_refuses_when_the_raw_gate_accepted(tmp_path):
    """Regression guard: the pre-existing refusal must be unchanged."""
    table = {**ROUND_TABLE,
             "candidates": [{**ROUND_TABLE["candidates"][0], "verdict": "accept"}]}
    run_dir, work = _run_dir_with_round_table(tmp_path, table=table)
    p = _commit_with_basis(run_dir, work, "gate")
    assert p.returncode == 2, f"commit.py did not refuse: {p.stdout}"
    err = json.loads(p.stdout)
    assert "ACCEPTED" in err["error"]


def test_reject_basis_drift_control_accepts_when_control_relative_says_reject(tmp_path):
    """The new, structured path: the raw gate accepted, but the round's drift-corrected
    control_relative comparison rejected and is verdict-stable -> drift_control is accepted."""
    table = {**ROUND_TABLE, "candidates": [{
        **ROUND_TABLE["candidates"][0], "verdict": "accept",
        "control_relative": {"reference": "ctl_null_i0", "gate_delta": -0.05,
                             "gate_threshold": 0.03, "verdict": "reject"},
        "verdict_stable": True,
    }]}
    run_dir, work = _run_dir_with_round_table(tmp_path, table=table)
    p = _commit_with_basis(run_dir, work, "drift_control")
    assert p.returncode == 0, (
        f"commit.py refused a structured drift_control reject: {p.stdout}\n{p.stderr}")


def test_reject_basis_drift_control_refused_when_control_relative_did_not_reject(tmp_path):
    """drift_control asserts the control_relative comparison ITSELF rejected — ROUND_TABLE's
    fixture has it at 'accept', so this basis must still be refused."""
    run_dir, work = _run_dir_with_round_table(tmp_path)
    p = _commit_with_basis(run_dir, work, "drift_control")
    assert p.returncode == 2, f"commit.py did not refuse an unsupported drift_control basis: {p.stdout}"


def test_reject_basis_drift_control_refused_when_verdict_unstable(tmp_path):
    """A verdict that flips between control replicates (verdict_stable: false) is no evidence
    either way, so drift_control must not be allowed to rest on it."""
    table = {**ROUND_TABLE, "candidates": [{
        **ROUND_TABLE["candidates"][0], "verdict": "accept",
        "control_relative": {"reference": "ctl_null_i0", "gate_delta": -0.05,
                             "gate_threshold": 0.03, "verdict": "reject"},
        "verdict_stable": False,
    }]}
    run_dir, work = _run_dir_with_round_table(tmp_path, table=table)
    p = _commit_with_basis(run_dir, work, "drift_control")
    assert p.returncode == 2, f"commit.py did not refuse an unstable drift_control verdict: {p.stdout}"
