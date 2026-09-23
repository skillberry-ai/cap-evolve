"""Reproduced live: ``prepare_candidate.py -t cand_3 --source work/cand_2`` copies
``work/cand_2`` into ``work/cand_3`` and then calls ``harness.seed_framework_memory``,
whose ``_seed_journal`` OVERWRITES ``cand_3/JOURNAL.md`` with the run-level accumulator
(everything already folded in from EARLIER commits). If ``work/cand_2`` is still
UNCOMMITTED — its own freshly-appended ``## Iteration cand_2 — ...`` entry has not yet
been folded into the run-level journal by ``commit.py``'s ``_reconcile_journal`` — that
entry is silently dropped, with no error. ``commit.py`` is the only thing that folds a
candidate's in-progress entry into the run-level accumulator, and that happens ONLY on
commit, never on a bare copy.

The fix reuses the exact check ``commit.py`` already makes (``harness.pending_handover``)
to detect this and refuse by default, or copy the entry forward when the caller passes
``--allow-uncommitted-source``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

sys.path.insert(0, str(CORE))

from cap_evolve import RunDir, harness  # noqa: E402

CAND2_ENTRY = "## Iteration cand_2 — added a rate-limit guard to the booking tool"


def _run(argv):
    env = {**os.environ, "CAPEVOLVE_CORE": str(CORE)}
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=env)


def _staged_run_with_uncommitted_source(tmp_path):
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="prep")
    src = run_dir.root / "work" / "cand_2"
    src.mkdir(parents=True)
    # An uncommitted work dir's JOURNAL.md: the run-level seed text, the marker, and the
    # optimizer's own just-written entry below it — never folded into run_dir/JOURNAL.md
    # because cand_2 was never passed through commit.py.
    (src / "JOURNAL.md").write_text(
        harness._JOURNAL_SEED + "\n\n" + harness._JOURNAL_MARK + "\n\n" + CAND2_ENTRY + "\n",
        encoding="utf-8")
    return run_dir, src


def test_prepare_candidate_refuses_an_uncommitted_source_by_default(tmp_path):
    run_dir, src = _staged_run_with_uncommitted_source(tmp_path)

    p = _run([str(SCRIPTS / "prepare_candidate.py"), "-r", str(run_dir.root), "-t", "cand_3",
              "--source", str(src)])

    assert p.returncode != 0, (
        f"prepare_candidate.py silently copied an uncommitted source's journal entry "
        f"away: {p.stdout}\n{p.stderr}")
    out = json.loads(p.stdout)
    assert "uncommitted" in out.get("error", "")
    assert "--allow-uncommitted-source" in out.get("error", "")
    assert not (run_dir.root / "work" / "cand_3").exists()


def test_allow_uncommitted_source_carries_the_entry_forward(tmp_path):
    run_dir, src = _staged_run_with_uncommitted_source(tmp_path)

    p = _run([str(SCRIPTS / "prepare_candidate.py"), "-r", str(run_dir.root), "-t", "cand_3",
              "--source", str(src), "--allow-uncommitted-source"])

    assert p.returncode == 0, f"prepare_candidate.py failed: {p.stdout}\n{p.stderr}"
    dest_journal = (run_dir.root / "work" / "cand_3" / "JOURNAL.md").read_text(encoding="utf-8")
    assert CAND2_ENTRY in dest_journal, (
        "cand_2's uncommitted journal entry did not survive into cand_3 even with "
        "--allow-uncommitted-source")


def test_provisional_committed_snapshot_is_not_refused(tmp_path):
    """Found by review: ``commit.py --decision provisional`` deliberately skips
    ``record_iteration`` (the iteration is not over — ``grow.py`` still owes it a real
    accept/reject/inconclusive commit later), so its journal entry is NEVER folded into
    the run-level accumulator by the normal path. ``pending_handover`` therefore reports
    it as pending forever, identically to a genuinely uncommitted ``work/`` dir — even
    though ``candidates/<id>`` IS a committed snapshot, exactly what --source's own
    docstring says it should normally be. Must not be refused, and must not require
    --allow-uncommitted-source."""
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="prep2")
    provisional_entry = "## Iteration cand_p — a directionally-positive but unresolved edit"
    workdir = run_dir.root / "work" / "cand_p"
    workdir.mkdir(parents=True)
    (workdir / "JOURNAL.md").write_text(
        harness._JOURNAL_SEED + "\n\n" + harness._JOURNAL_MARK + "\n\n" + provisional_entry + "\n",
        encoding="utf-8")
    run_dir.snapshot("cand_p", workdir)
    run_dir.log_event("provisional", candidate="cand_p", val=0.5, verdict="provisional")

    src = run_dir.candidate_dir("cand_p")
    p = _run([str(SCRIPTS / "prepare_candidate.py"), "-r", str(run_dir.root), "-t", "cand_q",
              "--source", str(src)])

    assert p.returncode == 0, (
        f"prepare_candidate.py refused a legitimately-committed provisional snapshot: "
        f"{p.stdout}\n{p.stderr}")
    out = json.loads(p.stdout)
    assert out.get("provisional_source") is True
    dest_journal = (run_dir.root / "work" / "cand_q" / "JOURNAL.md").read_text(encoding="utf-8")
    assert provisional_entry in dest_journal, (
        "cand_p's provisional journal entry did not survive into cand_q")


def test_provisional_snapshot_superseded_by_a_real_decision_is_unaffected(tmp_path):
    """Once grow.py's follow-up commit gives cand_p a REAL decision (accept/reject/
    inconclusive), record_iteration runs and folds its entry normally — the provisional
    auto-carry-forward path must not misfire on an already-reconciled snapshot."""
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="prep3")
    entry = "## Iteration cand_p — later resolved as a real reject"
    workdir = run_dir.root / "work" / "cand_p"
    workdir.mkdir(parents=True)
    (workdir / "JOURNAL.md").write_text(
        harness._JOURNAL_SEED + "\n\n" + harness._JOURNAL_MARK + "\n\n" + entry + "\n",
        encoding="utf-8")
    run_dir.snapshot("cand_p", workdir)
    run_dir.log_event("provisional", candidate="cand_p", val=0.5, verdict="provisional")
    # The follow-up real decision: folds the entry into the run-level journal for real.
    harness.record_iteration(run_dir, run_dir.candidate_dir("cand_p"), "cand_p",
                             parent_id="seed", accepted=False, reason="reject", val=0.5)
    run_dir.log_event("reject", candidate="cand_p", val=0.5, verdict="reject")

    src = run_dir.candidate_dir("cand_p")
    p = _run([str(SCRIPTS / "prepare_candidate.py"), "-r", str(run_dir.root), "-t", "cand_r",
              "--source", str(src)])

    assert p.returncode == 0, f"prepare_candidate.py failed: {p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout)
    assert out.get("provisional_source") is False
    assert out.get("uncommitted_source_journal_carried_forward") is False
