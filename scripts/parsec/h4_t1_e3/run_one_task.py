#!/usr/bin/env python3
"""Run exactly ONE task's baseline-only eval, as a single foreground
child process, then exit.

This arm never runs cap-evolve's
algorithm loop -- every task gets exactly one baseline eval of the SAME merged-bundle
capability (artifacts/v4/t4-merge/), scored zero-shot. That is the whole
experiment: no optimizing, no finalize, no test-split reveal beyond what
baseline.py itself does (it only ever touches "val" -- see harness.baseline()).

This drives skills/phases/baseline/scripts/run.py DIRECTLY via sys.executable,
not through `cap-evolve run` or the installed `cap-evolve` CLI tool. Three
reasons, confirmed by reading cli.py/harness.py/check.py/_bootstrap.py in
full:

  1. `cap-evolve run`'s finalize() unconditionally runs a first real
     evaluation on "test" even when best == baseline (there is no algorithm
     step to produce a different candidate here -- max_iterations is 0), and
     Adapter.tasks() ignores the split argument for a single-task project
     (train == val == test) -- so `cap-evolve run` would silently produce
     2x n_trials real trials per task, not n_trials.
  2. baseline.py's own hard gate (run_check) and RunDir/harness invocation is
     the exact single evaluation this experiment needs -- one call, one
     baseline.json, no finalize.
  3. Invoking it via sys.executable from THIS worktree's own
     skills/phases/baseline/scripts/run.py means _bootstrap.py resolves
     `cap_evolve` from THIS worktree's own core/ (it walks up from its own
     file location, and only defers to a global install if CAPEVOLVE_CORE is
     explicitly set) -- so there's no dependency on, or risk from, whatever
     cap-evolve version happens to be installed globally as a `uv tool`.

150 total real trials across the whole sweep: 30 tasks x 5 trials
(--n-trials 5), each task's ONE baseline() call -- never 340.

Usage:
    python3 scripts/parsec/h4_t1_e3/run_one_task.py               # next pending task
    python3 scripts/parsec/h4_t1_e3/run_one_task.py --task-id X   # a specific task

External repetition (run from the repo root):
    while python3 scripts/parsec/h4_t1_e3/run_one_task.py; do :; done

INVARIANT that recipe depends on: run_task() returns 0 only when the run it
launched actually wrote baseline.json (run.py writes this right after
harness.baseline() returns, unconditionally on success -- see
resolve_next_task_id(), which reads it as the "done" marker). If a future
edit ever makes run_task() return 0 without baseline.json existing, this loop
spins forever on that one task.

Exit codes:
    0  the task's baseline eval completed (baseline.json written) -- or ALL_DONE
    3  the task's project has a missing/dangling `adapters` symlink
    4  another parsec run holds the single-lane lock; nothing attempted
    5  the shared simulation stack is not healthy; nothing was attempted
    *  anything else is run.py's own exit code, passed through

Or, to survive the terminal closing / the machine sleeping less easily:
    caffeinate -i python3 -c '
    import subprocess, sys
    while True:
        rc = subprocess.call(["python3", "scripts/parsec/h4_t1_e3/run_one_task.py"])
        if rc != 0:
            sys.exit(rc)
    '
"""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
PROGRESS_LOG_NAME = "h4_t1_e3_progress.log"
# Deliberately the SAME lock file v4_t2_e1 uses: the resource it protects is
# the shared live stack (parsec-live + 5 MCP services), identical regardless
# of which task-family script is holding it. Two families running at once
# would contend for the same stack exactly like two v4_t2_e1 runs would.
LOCK_NAME = "v4_t2_e1.lock"
BASELINE_SCRIPT = REPO_ROOT / "skills" / "phases" / "baseline" / "scripts" / "run.py"
N_TRIALS = 5

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight_check  # noqa: E402
from scaffold_projects import TASK_IDS  # noqa: E402


def _log(msg: str, capevolve_dir: Path = CAPEVOLVE_DIR) -> None:
    """Append one timestamped line to ``capevolve_dir``'s progress log.

    ``capevolve_dir`` is a parameter, not the module global, for the same
    reason as v4_t2_e1's run_one_task.py: a test's tmp dir must never bleed
    lines into the real progress record.
    """
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    capevolve_dir.mkdir(parents=True, exist_ok=True)
    with open(capevolve_dir / PROGRESS_LOG_NAME, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def resolve_next_task_id(capevolve_dir: Path, task_ids: list[str]) -> str | None:
    for task_id in task_ids:
        task_root = capevolve_dir / f"h4_t1_e3_{task_id}"
        if not task_root.exists():
            return task_id
        # baseline.json, not final.json: this driver never calls finalize(),
        # so final.json is never written. baseline.json is run.py's own
        # unconditional success marker (written right after harness.baseline()
        # returns), which is exactly "did this task's one eval complete".
        done = any((run_dir / "baseline.json").exists() for run_dir in task_root.glob("run_*"))
        if not done:
            return task_id
    return None


def run_task(task_id: str, *, capevolve_dir: Path = CAPEVOLVE_DIR,
             repo_root: Path = REPO_ROOT, n_trials: int = N_TRIALS) -> int:
    task_base = capevolve_dir / f"h4_t1_e3_{task_id}"
    project = task_base / "project"

    # Single-lane enforcement, same mechanism and same LOCK_NAME as
    # v4_t2_e1 -- see the module docstring for why sharing the lock file is
    # correct here, not a bug.
    capevolve_dir.mkdir(parents=True, exist_ok=True)
    lock_path = capevolve_dir / LOCK_NAME
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _log(
            f"ABORT: another parsec run is already in flight (lock held at "
            f"{lock_path}) -- the 5-service harness is single-lane; wait for it "
            f"to finish.",
            capevolve_dir,
        )
        lock_file.close()
        return 4

    try:
        # Same dangling-symlink guard as v4_t2_e1's run_task(), scoped to just
        # `adapters` -- this arm has no `optimizer` symlink at all (see
        # scaffold_projects.py's module docstring for why).
        link = project / "adapters"
        if not link.exists():
            _log(
                f"ABORT: {task_id}'s 'adapters' symlink at {link} is missing or "
                f"dangling (does not resolve) -- re-run scaffold_projects.py "
                f"after confirming scripts/parsec/v4_t2_e1/common/adapters exists.",
                capevolve_dir,
            )
            return 3

        # Mirrors cli.py's own invocation convention exactly (read in full):
        # proj_abs = project.resolve(); workdir = proj_abs.parent.parent
        # (the .capevolve/ dir); every path arg passed to the subprocess is
        # relative to workdir, and the subprocess itself runs with
        # cwd=str(workdir). Matching this is what makes run.py's own
        # project-relative fallbacks (split_ids, capability path) resolve
        # exactly like they would under `cap-evolve run`.
        proj_abs = project.resolve()
        workdir = proj_abs.parent.parent  # .capevolve/
        base_rel = str(proj_abs.parent.relative_to(workdir))       # h4_t1_e3_<task>
        project_rel = str(proj_abs.relative_to(workdir))            # h4_t1_e3_<task>/project

        cmd = [
            sys.executable, str(BASELINE_SCRIPT),
            "--base", base_rel,
            "--project", project_rel,
            "--capability", "seed_capability",
            "--split-ids", "split_ids.json",
            "--n-trials", str(n_trials),
            "--seed", "0",
            "--spec", str((proj_abs / "capevolve.yaml").relative_to(workdir)),
        ]

        env = dict(os.environ)
        env["TASK_ID"] = task_id

        _log(f"starting {task_id}: {' '.join(cmd)} (cwd={workdir})", capevolve_dir)
        proc = subprocess.run(cmd, env=env, cwd=str(workdir))
        _log(f"finished {task_id}: exit={proc.returncode}", capevolve_dir)
        return proc.returncode
    finally:
        # In a finally, not on the success path: a lock left held would wedge
        # the whole remaining sweep behind a single crashed run.
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default=None,
                         help="run this specific task id instead of the next pending one")
    # Topping a task up to five CLEAN trials, rather than re-running all five,
    # is what this is for: trials lost to infra (a refused seed, a dropped
    # connection) produce no reward at all, so the survivors are still valid
    # measurements and only the shortfall needs re-running. The top-up lands in
    # its own run_* dir; collect_results.py unions valid trials across a task's
    # run dirs, so 2 valid + 3 topped up reads as the 5 it is.
    parser.add_argument("--n-trials", type=int, default=N_TRIALS,
                         help=f"trials to run (default {N_TRIALS}); use less to top "
                              f"up a task that lost trials to infra errors")
    args = parser.parse_args()
    if args.n_trials < 1 or args.n_trials > N_TRIALS:
        parser.error(f"--n-trials must be between 1 and {N_TRIALS}")

    capevolve_dir = CAPEVOLVE_DIR

    # No installed_cli_supports_stop_at_reward() gate here -- this driver
    # never shells out to the `cap-evolve` CLI tool at all (it invokes
    # baseline/scripts/run.py directly via sys.executable from THIS
    # worktree), so there is nothing about a stale global install for it to
    # check. See preflight_check.py's module docstring.
    healthy, unreachable = preflight_check.stack_is_healthy()
    if not healthy:
        _log(
            f"ABORT: simulation stack is not healthy -- unreachable: "
            f"{', '.join(unreachable)}. Bring the harness/parsec-live services up "
            f"before starting a task; every trial against a broken stack scores "
            f"0.0 and is indistinguishable from a capability failure afterwards.",
            capevolve_dir,
        )
        return 5

    task_id = args.task_id or resolve_next_task_id(capevolve_dir, TASK_IDS)
    if task_id is None:
        _log("ALL_DONE: every h4_t1_e3 task has a baseline.json", capevolve_dir)
        return 0
    if task_id not in TASK_IDS:
        _log(f"ABORT: unknown task id {task_id!r}", capevolve_dir)
        return 2

    return run_task(task_id, capevolve_dir=capevolve_dir, n_trials=args.n_trials)


if __name__ == "__main__":
    sys.exit(main())
