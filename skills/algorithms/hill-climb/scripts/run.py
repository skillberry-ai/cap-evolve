"""hill-climb — global hill-climb on the val gate, with a selectable focus schedule.

One skill replacing the three byte-identical clones (all-at-once / cyclic /
hardest-first); they differed ONLY in which train tasks each iteration's
reflection emphasizes. ``--focus`` selects that schedule:

    all            propose against the whole train set each iteration (default)
    cyclic         focus one train task at a time, cycling through them
    hardest-first  rank train tasks by baseline score ascending, attack hardest first

The parent is always the current best (global hill-climb); honesty (val-only
gate, sealed test) lives in core. This is a thin wrapper over
``harness.hill_climb_loop(focus=...)``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.store import make_store
from cap_evolve.check import load_adapter
from cap_evolve.loop import SplitResult

FOCUS_CHOICES = ("all", "cyclic", "hardest-first")
ALGO = "hill-climb"

# Back-compat: accept the old skill names as --focus values and translate.
_LEGACY_FOCUS = {"all-at-once": "all", "cyclic": "cyclic", "hardest-first": "hardest-first"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=ALGO)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--optimizer", required=True, help="optimizer cmd with {workdir} {prompt}")
    p.add_argument("--focus", default="all",
                   help="schedule: all | cyclic | hardest-first (old skill names accepted)")
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--gate-mode", default="auto",
                   help="auto = let the engine pick the paired gate (recommended; candidate & current share val tasks); or significant|paired|strict|threshold")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--store", default="git", help="git|copy|command")
    p.add_argument("--store-commit-cmd", default=None)
    p.add_argument("--no-regression", action="store_true",
                   help="reject candidates that break a passing val task")
    p.add_argument("--resume", action="store_true",
                   help="continue from the run's current best candidate (read its val "
                        "from rollouts) instead of baseline")
    p.add_argument("--capabilities", default="",
                   help="comma-separated capability skills under optimization (e.g. "
                        "'system-prompt,tools'); surfaced to the optimizer so it knows "
                        "the allowed edit space")
    p.add_argument("--instructions-file", default=None,
                   help="optimizer-instructions template (intake-authored) to render the "
                        "per-iteration prompt from; defaults to the shipped template")
    p.add_argument("--bench-repo", default=None,
                   help="path to the benchmark/runner source, surfaced to the optimizer "
                        "as read-only context")
    p.add_argument("--optimizer-name", default=None,
                   help="resolved optimizer name (registry row); used to copy that "
                        "optimizer's features reference into the optimizer workdir")
    p.add_argument("--capability-sources", default="",
                   help="comma-separated supporting source files (data models / types "
                        "the tools import) copied verbatim into the optimizer's "
                        "./guidance/sources/; resolved relative to --project")
    p.add_argument("--target-model", default="",
                   help="consuming/runtime model id or tier keyword (frontier|strong|mid|weak)")
    p.add_argument("--target-profile-file", default=None,
                   help="optional project-local brief overriding the tier's built-in brief")
    args = p.parse_args(argv)

    focus = _LEGACY_FOCUS.get(args.focus, args.focus)
    if focus not in FOCUS_CHOICES:
        print(json.dumps({"error": f"unknown --focus {args.focus!r}; choose from {FOCUS_CHOICES}"}))
        return 2

    run_dir = RunDir.open(Path(args.run_dir))
    store = make_store({"store": args.store, "store_commit_cmd": args.store_commit_cmd}, run_dir.root)
    adapter = load_adapter(Path(args.project))
    optimizer = harness.optimizer_from_command(shlex.split(args.optimizer))
    if args.resume and run_dir.best_id:
        current_val = harness.split_result_from_rollouts(run_dir, run_dir.best_id, "val")
    else:
        current_val = SplitResult.from_dict(
            json.loads((run_dir.root / "baseline.json").read_text())["val"])

    result = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=current_val,
        focus=focus, max_iterations=args.max_iterations, n_trials=args.n_trials,
        gate_kwargs=({"k_se": args.k_se} if args.gate_mode == "auto"
                     else {"mode": args.gate_mode, "k_se": args.k_se}),
        algorithm=f"{ALGO}:{focus}", no_regression=args.no_regression, store=store,
        capabilities=[c.strip() for c in args.capabilities.split(",") if c.strip()],
        instructions_file=args.instructions_file, bench_repo=args.bench_repo,
        optimizer_name=args.optimizer_name,
        capability_sources=[s.strip() for s in args.capability_sources.split(",") if s.strip()],
        project_dir=Path(args.project),
        target_model=args.target_model,
        target_profile_file=args.target_profile_file,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
