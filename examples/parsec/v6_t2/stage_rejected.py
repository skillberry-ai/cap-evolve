#!/usr/bin/env python3
"""Stage the most recently rejected candidate's trials into an optimizer workdir.

Runs as the first step of the v6_t2 claude-code optimizer row (``registry.yaml`` beside this
file), with cwd = the iteration's workdir ``<run>/work/<cand>/``. cap-evolve itself already puts
the parent's own trials in ``./trajectories/`` (the Seed's, then the champion's after an accept);
this adds the other half of the v6_t2 design: what the last REJECTED edit did to the agent.

    ./trajectories/rejected/<task>__<cand>__t*.json   that candidate's val trials on this task

Inside ``trajectories/`` on purpose: cap-evolve excludes that directory from the capability
(``types.NON_CAPABILITY_DIRS``), so the staged trials are never diffed, hashed, or shipped as part
of the candidate.

The rejected candidate's edit is already in ``./prior_iterations/<cand>/diff.patch`` (written by
cap-evolve's RUNMAP step), so the trials and the edit that produced them sit side by side. When
nothing has been rejected yet, nothing is staged and the directory is absent.

Reads only this run's own files, and only the ``val`` split, which in a v6_t2 project is the one
task being optimized: no other task's or split's trials can reach the optimizer this way.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def last_rejected(run: Path) -> str | None:
    events = run / "events.jsonl"
    if not events.is_file():
        return None
    cand = None
    for line in events.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("kind") == "step" and rec.get("candidate") and not rec.get("accept"):
            cand = str(rec["candidate"])
    return cand


def main() -> int:
    workdir = Path.cwd()
    run = workdir.parents[1]            # <run>/work/<cand>
    if not (run / "state.json").is_file():
        print(f"stage_rejected: {run} is not a cap-evolve run dir; nothing staged", file=sys.stderr)
        return 0
    dst = workdir / "trajectories" / "rejected"
    shutil.rmtree(dst, ignore_errors=True)
    cand = last_rejected(run)
    if cand is None:
        return 0
    files = sorted((run / "rollouts" / "val").glob(f"*__{cand}__t*.json"))
    if not files:
        return 0
    dst.mkdir(parents=True)
    for f in files:
        shutil.copyfile(f, dst / f.name)
    print(f"stage_rejected: {len(files)} trials of rejected {cand}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
