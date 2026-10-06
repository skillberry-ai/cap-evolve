"""prepare_candidate — cp -r a candidate snapshot into work/<tag> AND seed the framework
memory files into it, in one step.

SKILL.md step 2 used to teach a bare ``cp -r "$R/candidates/$BEST" "$R/work/$TAG"``: that
copies whatever is (or is not) already under ``candidates/$BEST``, with no guarantee the
memory files (LEDGER.md/JOURNAL.md/RUNMAP.md/PROCESS.md) are in there to copy — host.py's
``_stage_context`` and commit.py only ever re-seed the CURRENT BEST candidate's snapshot, so
a workdir built any other way got a working copy that never carried them. Confirmed live on
run_20260922_154227: none of ``work/cand_1`` through ``work/cand_4`` had them.

This is the single wrapper the skill points at instead: copy, then call
``harness.seed_framework_memory`` on the destination, so the promise holds regardless of
what the source dir happened to have.

``--source`` should normally be a committed ``candidates/<id>`` snapshot, not a live
``work/<tag>`` dir: ``seed_framework_memory`` OVERWRITES ``dest/JOURNAL.md`` with the
run-level accumulator (everything already reconciled from EARLIER commits), discarding
whatever the source's own copy held. A committed snapshot's journal entry is already
folded into the run-level accumulator by then (``commit.py``), so nothing is lost — but
an UNCOMMITTED ``work/`` dir's freshly-appended entry is not, and copying from it here
would silently drop that entry with no error. This is detected below and refused unless
``--allow-uncommitted-source`` is passed (which copies the entry forward instead of
losing it).

One committed snapshot is an exception to "already folded by then": a ``--decision
provisional`` candidate (Δ>0 but unresolved — ``commit.py`` deliberately skips
``record_iteration`` for it, since the iteration is not over until ``grow.py`` re-gates
it). Its journal entry is never folded by the normal path either, so it looks identical
to a genuinely uncommitted source — ``_is_provisional_snapshot`` tells the two apart via
the audit log and carries the entry forward automatically, the same as
``--allow-uncommitted-source``, without requiring the flag.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import RunDir, harness


def _is_provisional_snapshot(run_dir: RunDir, src: Path) -> bool:
    """True if ``src`` is a ``candidates/<id>`` snapshot whose latest decision event is
    ``provisional`` — a candidate ``commit.py`` deliberately left mid-iteration (Δ>0 but
    unresolved; ``grow.py`` still owes it a real accept/reject/inconclusive commit later).

    ``commit.py`` skips ``record_iteration`` for a provisional decision on purpose (the
    iteration is not over), so its journal entry is NEVER folded into the run-level
    accumulator by the normal path — ``pending_handover`` reports it as pending forever,
    identically to a genuinely uncommitted ``work/`` dir it is not. Distinguishing the two
    needs the audit log, not the journal file itself: a committed snapshot under
    ``candidates/`` whose own id has a logged ``provisional`` decision is legitimate and
    safe to carry forward (same effect as ``--allow-uncommitted-source``), not a caller
    forgetting to commit.
    """
    try:
        if src.parent != run_dir.root / "candidates":
            return False
    except (ValueError, OSError):
        return False
    cid = src.name
    events_path = run_dir.root / "events.jsonl"
    if not events_path.exists():
        return False
    latest = None
    with events_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:  # noqa: BLE001 — a torn line carries no decision
                continue
            if ev.get("kind") in ("accept", "reject", "inconclusive", "provisional") and \
                    ev.get("candidate") == cid:
                latest = ev.get("kind")
    return latest == "provisional"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="prepare_candidate")
    p.add_argument("-r", "--run-dir", required=True)
    p.add_argument("-t", "--tag", required=True,
                   help="new candidate tag; destination is work/<tag>")
    p.add_argument("--source", default=None,
                   help="dir to copy from; default = candidates/<best_id> (or candidates/seed "
                        "if the run has no baseline yet). Should normally be a committed "
                        "candidates/<id> snapshot, NOT a live work/<tag> dir — an uncommitted "
                        "work dir's own freshly-appended journal entry is not yet folded into "
                        "the run-level journal, and seed_framework_memory would silently "
                        "overwrite it away (see --allow-uncommitted-source).")
    p.add_argument("--allow-uncommitted-source", action="store_true",
                   help="--source is an uncommitted work dir with a journal entry not yet "
                        "folded into the run's journal; copy that entry forward into dest "
                        "instead of refusing.")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    src = Path(args.source) if args.source else run_dir.candidate_dir(run_dir.best_id or "seed")
    if not src.is_dir():
        print(json.dumps({"error": f"source dir not found: {src}"}, indent=2))
        return 2
    dest = run_dir.root / "work" / args.tag
    if dest.exists():
        print(json.dumps({"error": f"destination already exists: {dest}"}, indent=2))
        return 2

    # seed_framework_memory (below) overwrites dest/JOURNAL.md with the run-level
    # accumulator. If src is an uncommitted work dir whose own journal entry is not yet
    # folded into that accumulator (only commit.py folds it, via _reconcile_journal),
    # that entry would be silently lost. pending_handover is the same check commit.py
    # itself uses to decide whether there is a real handover to fold.
    pending = harness.pending_handover(src, run_dir)
    provisional_source = bool(pending) and _is_provisional_snapshot(run_dir, src)
    if pending and not args.allow_uncommitted_source and not provisional_source:
        print(json.dumps({
            "error": "source has an uncommitted journal entry not yet folded into the "
                     "run's journal — commit it first via commit.py, or pass "
                     "--allow-uncommitted-source to copy it forward anyway",
            "source": str(src),
        }, indent=2))
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    written = harness.seed_framework_memory(dest, run_dir)
    if pending:
        journal = dest / "JOURNAL.md"
        journal.write_text(journal.read_text(encoding="utf-8").rstrip() + "\n\n" + pending + "\n",
                           encoding="utf-8")
    print(json.dumps({"tag": args.tag, "source": str(src), "dest": str(dest),
                      "memory_written": written,
                      "uncommitted_source_journal_carried_forward": bool(pending),
                      "provisional_source": provisional_source}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
