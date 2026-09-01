"""An agent-mode run accumulated no learning across its rounds — two independent holes.

Both observed on smoke spreadsheetbench run 33046360451 (and 32971129203 before it), and both
are about the loop's memory of ITSELF, which is the thing that is supposed to make round 3
better than round 1.

1. **Optimizer memory was empty.** ``rejected.jsonl`` / ``history.jsonl`` back the dashboard's
   Memory panel (``memory.py``'s docstring names it) and are written by every DETERMINISTIC
   algorithm — ``harness``'s hill-climb, ``gepa``, ``skillopt`` all call ``RejectedMemory.add`` /
   ``History.add`` inline. Agent mode books its rounds through ``commit.py``, which never did, so
   the panel published ``{"history": [], "rejected": []}`` for the whole run.

2. **Every round's handover said "(no handover written by the optimizer)".** ``JOURNAL.md`` is
   two halves: the framework stamps an objective RESULT line (outcome + the exact tasks
   broke/fixed), and the optimizer appends the INTENT above it — what it tried, why, and which
   hypotheses prior RESULTs already refuted. ``_reconcile_journal`` folds the intent half out of
   ``<workdir>/JOURNAL.md``. Nothing ever told the agent to write it: ``host.py`` says only that
   ``commit.py`` "reconciles it as you book rounds, so it accrues your own history and is worth
   reading from round 2 on" — true of the RESULT half, false of the half the agent owns. So from
   round 2 the agent could read WHICH task it broke but never WHAT IT HAD TRIED, and the
   journal's own standing instruction ("never re-test a refuted idea") was unfollowable.

The fix for (2) needs no core change: ``_journal_tail`` already falls back to the last
``## Iteration`` block when the marker is absent, so an agent that writes the file at all is
folded in correctly. What was missing was being asked, and being told when it forgot.
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


def _staged(tmp_path, cid="cand_1"):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    work = run_dir.root / "work" / cid
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)
    return run_dir, work


def _commit(run_dir, work, *extra, cid="cand_1", decision="reject", val="0.4967"):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", cid, "--from-dir", str(work),
         "--decision", decision, "--val", val,
         "--note", "compute-not-hardcode replay + over-write contract", *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"
    return json.loads(p.stdout)


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- 1. optimizer memory -----------------------------------------------------------------

def test_a_rejected_round_lands_in_the_memory_the_dashboard_publishes(tmp_path):
    run_dir, work = _staged(tmp_path)
    _commit(run_dir, work)

    rejected = _jsonl(Path(run_dir.rejected_path))
    assert rejected, (
        "the round was rejected and left no trace in rejected.jsonl, so the dashboard's Memory "
        "panel publishes {} for the whole run and the next round cannot see what was refuted")
    rec = rejected[-1]
    assert rec["candidate_id"] == "cand_1"
    assert rec.get("val") == 0.4967, f"the rejected candidate's val was dropped: {rec}"
    assert "compute-not-hardcode" in (rec.get("reason") or ""), (
        f"the reason the round was rejected is not recorded: {rec}")


def test_an_accepted_round_lands_in_history(tmp_path):
    run_dir, work = _staged(tmp_path, cid="cand_2")
    _commit(run_dir, work, cid="cand_2", decision="accept", val="0.54")

    hist = _jsonl(Path(run_dir.history_path))
    assert hist, "an accepted round left no lineage in history.jsonl"
    assert hist[-1]["candidate_id"] == "cand_2" and hist[-1]["val"] == 0.54
    assert not _jsonl(Path(run_dir.rejected_path)), (
        "an ACCEPTED candidate was filed as rejected — that teaches the next round to avoid "
        "the one edit that worked")


# --- 2. the handover half of the journal -------------------------------------------------

HANDOVER = """## Iteration cand_1 — compute-not-hardcode replay + over-write contract
- Changes I made: prompt.md (replay rationale), task_template.md (write-only-required-cells)
- Refuted hypotheses: none yet
- Focus next iteration: the TYPE cluster
"""


def test_a_handover_the_agent_wrote_is_folded_into_the_run_journal(tmp_path):
    """The mechanism already worked — this pins it, because the guidance fix depends on it."""
    run_dir, work = _staged(tmp_path)
    (work / "JOURNAL.md").write_text(HANDOVER, encoding="utf-8")
    _commit(run_dir, work)

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "compute-not-hardcode replay + over-write contract" in journal
    assert "no handover written by the optimizer" not in journal, (
        "the agent DID write a handover and it was still recorded as absent")
    assert "RESULT (framework, objective)" in journal, "the framework RESULT half is missing"


def test_a_missing_handover_is_reported_back_to_the_agent(tmp_path):
    """``commit.py`` is the only thing the agent runs every round, so it is the only place a
    forgotten handover can be surfaced while there are still rounds left to fix it. Silence is
    what produced three straight rounds of "(no handover written by the optimizer)"."""
    run_dir, work = _staged(tmp_path)
    out = _commit(run_dir, work)

    assert out.get("handover_recorded") is False, (
        f"commit.py did not report that the round booked no handover: {out}")
    warns = " ".join(out.get("warnings") or [])
    assert "JOURNAL.md" in warns, (
        f"nothing told the agent where to write its handover next round: {out}")


def test_the_handover_flag_is_true_when_one_was_written(tmp_path):
    run_dir, work = _staged(tmp_path)
    (work / "JOURNAL.md").write_text(HANDOVER, encoding="utf-8")
    out = _commit(run_dir, work)

    assert out.get("handover_recorded") is True, f"a written handover reported as missing: {out}"
    assert not [w for w in (out.get("warnings") or []) if "JOURNAL" in w], (
        f"warned about a handover that was in fact written: {out}")


def test_a_stale_handover_carried_over_from_the_last_round_is_not_reported_as_written(tmp_path):
    """An agent's next working copy is usually a COPY of the last one, so it arrives with the
    previous round's JOURNAL entry already in it. ``_reconcile_journal`` refuses to book the
    same entry twice (it books the "duplicate handover" placeholder instead), so reporting
    that entry as this round's handover warns nobody about the round that actually lost one."""
    run_dir, work = _staged(tmp_path)
    (work / "JOURNAL.md").write_text(HANDOVER, encoding="utf-8")
    _commit(run_dir, work)                       # round 1: the entry is booked

    work2 = run_dir.root / "work" / "cand_2"     # round 2: cloned, and NOT updated
    shutil.copytree(work, work2)
    out = _commit(run_dir, work2, cid="cand_2")

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "duplicate handover" in journal, (
        "the dedup guard changed: this test is about agreeing with what it books")
    assert "EMPTY HANDOVER" not in journal, (
        "a stale entry is a DUPLICATE, not an empty handover: the escalation path would "
        "synthesize an entry from the commit reason and log optimizer_context_warning")
    assert out.get("handover_recorded") is False, (
        f"a stale entry the journal refused to book was reported as this round's handover: {out}")


# --- 3. the guidance that asks for it ----------------------------------------------------

def test_the_host_tells_the_agent_to_write_the_handover():
    """Guidance, not plumbing, is why this was empty. The host brief is the agent's only
    instruction sheet for the parts of the loop it drives itself."""
    src = (SCRIPTS / "host.py").read_text(encoding="utf-8")
    assert "JOURNAL.md" in src
    lo = src.lower()
    assert "append" in lo and "handover" in lo, (
        "the host brief never asks the agent to APPEND its own handover entry — it only says "
        "the journal is worth READING, which is how every round booked an empty intent half")
