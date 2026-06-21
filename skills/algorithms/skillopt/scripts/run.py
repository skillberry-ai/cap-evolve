"""skillopt — a disciplined single-lineage climber with a textual learning rate.

SkillOpt (arXiv:2605.23904) runs epochs × mini-batches: each step focuses the
optimizer on one mini-batch of train tasks under a shrinking integer **edit
budget** L (the textual learning rate, on a ``constant|linear|cosine`` schedule),
keeps a within-epoch rejected-edit + failure-pattern buffer in the prompt, and
ends each epoch with ONE extra *gated* slow/meta update that fixes longitudinal
regressions. Parent is always the current best (single lineage). Gated on val;
test sealed.

Thin wrapper over ``cap_evolve.skillopt.skillopt_loop``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness, skillopt
from cap_evolve.check import load_adapter
from cap_evolve.loop import SplitResult
from cap_evolve.store import make_store

ALGO = "skillopt"
SCHEDULES = ("constant", "linear", "cosine")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=ALGO)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--optimizer", required=True, help="optimizer cmd with {workdir} {prompt}")
    p.add_argument("--epochs", type=int, default=4)
    # Accepted (and ignored) for `cap-evolve run` compatibility: the generic
    # sequencer passes --max-iterations to every algorithm, but skillopt is
    # epoch-driven — set --epochs to control the step count.
    p.add_argument("--max-iterations", type=int, default=0,
                   help=argparse.SUPPRESS)
    p.add_argument("--batch-size", type=int, default=None,
                   help="train tasks per mini-batch (default min(8, len(train)))")
    p.add_argument("--accumulation", type=int, default=1,
                   help="mini-batches accumulated per step (default 1)")
    # the textual learning rate = integer edit budget; --lr is an alias
    p.add_argument("--edit-budget", "--lr", dest="edit_budget", type=int, default=4,
                   help="max edits per step at the start (textual learning rate)")
    p.add_argument("--min-edit-budget", type=int, default=2,
                   help="edit budget floor at the end of the schedule")
    p.add_argument("--lr-schedule", default="cosine", choices=SCHEDULES,
                   help="how the edit budget decays over the run")
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--gate-mode", default="auto",
                   help="auto = let the engine pick the paired gate (recommended; candidate & current share val tasks); or significant|paired|strict|threshold")
    p.add_argument("--k-se", type=float, default=1.0)
    su = p.add_mutually_exclusive_group()
    su.add_argument("--slow-update", dest="slow_update", action="store_true", default=True,
                    help="run the gated epoch-boundary slow/meta update (default on)")
    su.add_argument("--no-slow-update", dest="slow_update", action="store_false",
                    help="disable the slow update")
    p.add_argument("--slow-update-sample", type=int, default=20,
                   help="train ids sampled for the longitudinal slow-update compare")
    p.add_argument("--no-regression", action="store_true",
                   help="reject candidates that break a passing val task")
    p.add_argument("--store", default="git", help="git|copy|command")
    p.add_argument("--store-commit-cmd", default=None)
    p.add_argument("--resume", action="store_true",
                   help="continue from the run's current best instead of baseline")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    store = make_store({"store": args.store, "store_commit_cmd": args.store_commit_cmd}, run_dir.root)
    adapter = load_adapter(Path(args.project))
    optimizer = harness.optimizer_from_command(shlex.split(args.optimizer))
    if args.resume and run_dir.best_id:
        current_val = harness.split_result_from_rollouts(run_dir, run_dir.best_id, "val")
    else:
        current_val = SplitResult.from_dict(
            json.loads((run_dir.root / "baseline.json").read_text())["val"])

    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=current_val,
        epochs=args.epochs, batch_size=args.batch_size, accumulation=args.accumulation,
        edit_budget=args.edit_budget, min_edit_budget=args.min_edit_budget,
        lr_schedule=args.lr_schedule, n_trials=args.n_trials,
        gate_kwargs=({"k_se": args.k_se} if args.gate_mode == "auto"
                     else {"mode": args.gate_mode, "k_se": args.k_se}),
        no_regression=args.no_regression, slow_update=args.slow_update,
        slow_update_sample=args.slow_update_sample, algorithm=ALGO, store=store,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
