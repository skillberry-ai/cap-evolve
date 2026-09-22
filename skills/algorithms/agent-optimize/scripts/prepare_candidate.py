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
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import RunDir, harness


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="prepare_candidate")
    p.add_argument("-r", "--run-dir", required=True)
    p.add_argument("-t", "--tag", required=True,
                   help="new candidate tag; destination is work/<tag>")
    p.add_argument("--source", default=None,
                   help="dir to copy from; default = candidates/<best_id> (or candidates/seed "
                        "if the run has no baseline yet)")
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

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    written = harness.seed_framework_memory(dest, run_dir)
    print(json.dumps({"tag": args.tag, "source": str(src), "dest": str(dest),
                      "memory_written": written}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
