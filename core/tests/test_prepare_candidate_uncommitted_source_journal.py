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
