"""Confirmed bug, reproduced on run_20260922_154227 (still on disk): none of
``work/cand_1`` through ``work/cand_4`` had LEDGER.md/JOURNAL.md/RUNMAP.md/PROCESS.md,
because the only two call sites that seed ``harness.seed_framework_memory`` are the
harness's own internal materialize path and ``host.py``'s/``commit.py``'s re-seed of
``candidates/<best_id>/`` — and SKILL.md step 2's own documented pattern
(``cp -r "$R/candidates/$BEST" "$R/work/$TAG"``) is neither of those, so a driver
following it literally never gets the promise fulfilled unless the SOURCE dir happened
to carry the files already.

``harness.ensure_framework_memory`` is the defensive guard: screen.py, round.py and
commit.py each call it on the work/<tag> dir they operate on, seeding the files IFF any
are missing — regardless of how that dir was built (bare cp -r from a source that itself
lacked them, in every case here).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))

from test_round_requires_screen_ladder import _project, _run, _staged_run_dir  # noqa: E402
from test_agent_optimize_round_attribution import _run_dir_with_round_table  # noqa: E402

_MEMORY_FILES = ("LEDGER.md", "JOURNAL.md", "RUNMAP.md", "PROCESS.md")


def _assert_none_present(cand_dir: Path):
    missing = [f for f in _MEMORY_FILES if not (cand_dir / f).exists()]
    assert missing == list(_MEMORY_FILES), (
        f"fixture assumption violated — some memory files already present: "
        f"{set(_MEMORY_FILES) - set(missing)}")


def _assert_all_present_and_nonempty(cand_dir: Path, *, where: str):
    for f in _MEMORY_FILES:
        p = cand_dir / f
        assert p.exists(), f"{where} did not seed {f} into a bare-cp -r'd workdir"
        assert p.read_text(encoding="utf-8").strip(), f"{where} seeded {f} but left it empty"


def test_screen_seeds_missing_memory_files_into_a_bare_cp_workdir(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    cand_dir = work / "cand_1"
    _assert_none_present(cand_dir)

    p = _run([str(SCRIPTS / "screen.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidate", str(cand_dir), "--tier", "1"])
    assert p.returncode == 0, f"screen.py failed: {p.stdout}\n{p.stderr}"
    _assert_all_present_and_nonempty(cand_dir, where="screen.py")


def test_round_seeds_missing_memory_files_into_a_bare_cp_workdir(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    cand_dir = work / "cand_1"
    _assert_none_present(cand_dir)

    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
              "--skip-screen-ladder"])
    assert p.returncode == 0, f"round.py failed: {p.stdout}\n{p.stderr}"
    _assert_all_present_and_nonempty(cand_dir, where="round.py")


def test_commit_seeds_missing_memory_files_into_a_bare_cp_workdir(tmp_path):
    run_dir, work = _run_dir_with_round_table(tmp_path, table=None)
    _assert_none_present(work)

    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work),
         "--decision", "reject", "--val", "0.5333333333333333",
         "--note", "regression guard for the memory-seeding fix"],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(CORE)})
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"
    _assert_all_present_and_nonempty(work, where="commit.py")
