#!/usr/bin/env python3
"""Run exactly ONE v4_t2_e1 task's cap-evolve optimization to completion, as
a single foreground child process, then exit.

Deliberately NOT a loop over all 21 tasks: each invocation launches one
`cap-evolve run`, waits for it, records the outcome, and stops. This is what
makes a VPN drop, a sleep, or a crash cost at most the one task in flight —
the next invocation (run by hand, or from a trivial external loop) picks up
exactly where this one left off, via resolve_next_task_id().

Usage:
    python3 scripts/v4_t2_e1/run_one_task.py               # next pending task
    python3 scripts/v4_t2_e1/run_one_task.py --task-id X   # a specific task
    python3 scripts/v4_t2_e1/run_one_task.py --follow      # + --follow to cap-evolve run

External repetition (run from the repo root):
    while python3 scripts/v4_t2_e1/run_one_task.py; do :; done

Or, to survive the terminal closing / the machine sleeping less easily:
    caffeinate -i python3 -c '
    import subprocess, sys
    while True:
        rc = subprocess.call(["python3", "scripts/v4_t2_e1/run_one_task.py"])
        if rc != 0:
            sys.exit(rc)
    '
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
PROGRESS_LOG = CAPEVOLVE_DIR / "v4_t2_e1_progress.log"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight_check  # noqa: E402
from scaffold_projects import TASK_IDS  # noqa: E402


def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    CAPEVOLVE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def resolve_next_task_id(capevolve_dir: Path, task_ids: list[str]) -> str | None:
    for task_id in task_ids:
        task_root = capevolve_dir / f"v4_t2_e1_{task_id}"
        if not task_root.exists():
            return task_id
        done = any((run_dir / "final.json").exists() for run_dir in task_root.glob("run_*"))
        if not done:
            return task_id
    return None


def run_task(task_id: str, *, capevolve_dir: Path = CAPEVOLVE_DIR,
             repo_root: Path = REPO_ROOT, follow: bool = False) -> int:
    project = capevolve_dir / f"v4_t2_e1_{task_id}" / "project"

    # Task 2's _ensure_symlink() uses Path.symlink_to(), which does not
    # validate that its target exists — so a project scaffolded before its
    # common/ source existed can end up with a dangling `adapters` or
    # `optimizer` symlink and exit 0. Path.exists() follows symlinks and
    # returns False for a dangling one, which is exactly the failure mode
    # we need to catch here (is_symlink() alone would return True even when
    # dangling, so it can't be used for this check).
    for name in ("adapters", "optimizer"):
        link = project / name
        if not link.exists():
            _log(
                f"ABORT: {task_id}'s {name!r} symlink at {link} is missing or "
                f"dangling (does not resolve) — re-run scaffold_projects.py "
                f"after confirming its common source exists."
            )
            return 3

    cmd = ["cap-evolve", "run", "--project", str(project), "--dashboard", "off"]
    if follow:
        cmd.append("--follow")

    import os
    env = dict(os.environ)
    env["TASK_ID"] = task_id

    _log(f"starting {task_id}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, cwd=str(repo_root))
    _log(f"finished {task_id}: exit={proc.returncode}")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default=None,
                         help="run this specific task id instead of the next pending one")
    parser.add_argument("--follow", action="store_true",
                         help="pass --follow through to `cap-evolve run`")
    args = parser.parse_args()

    if not preflight_check.installed_cli_supports_stop_at_reward():
        _log("ABORT: installed cap-evolve tool is stale — see preflight_check.py output")
        preflight_check.main()
        return 2

    task_id = args.task_id or resolve_next_task_id(CAPEVOLVE_DIR, TASK_IDS)
    if task_id is None:
        _log("ALL_DONE: every v4_t2_e1 task has a final.json")
        return 0
    if task_id not in TASK_IDS:
        _log(f"ABORT: unknown task id {task_id!r}")
        return 2

    return run_task(task_id, follow=args.follow)


if __name__ == "__main__":
    sys.exit(main())
