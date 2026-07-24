"""gepa — the real GEPA sample-efficient reflective Pareto optimizer.

Thin wrapper: parse args, load the project adapter + the optimizer command, read
the baseline's full-val ``SplitResult`` from ``baseline.json`` (the seed is already
val-scored), and hand off to ``cap_evolve.gepa.gepa_loop``. All loop mechanics —
minibatch local gate, reflective dataset, per-instance frontier, system-aware
merge, eval cache, metric-call budget — live in core. Prints the result JSON.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, gepa, harness
from cap_evolve.check import load_adapter
from cap_evolve.loop import SplitResult
from cap_evolve.store import make_store

ALGO = "gepa"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=ALGO)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--optimizer", required=True, help="optimizer cmd with {workdir} {prompt}")
    p.add_argument("--max-metric-calls", type=int, default=0,
                   help="PRIMARY budget: total rollouts (minibatch + full-val); 0=unlimited")
    p.add_argument("--max-iterations", type=int, default=50,
                   help="SECONDARY cap on propose->gate iterations")
    p.add_argument("--minibatch-size", type=int, default=4)
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--component-selector", default="round_robin",
                   choices=("round_robin", "all"))
    p.add_argument("--selection-strategy", default="pareto_per_instance",
                   help="frontier parent picker (selection.py strategy)")
    p.add_argument("--max-merges", type=int, default=2)
    p.add_argument("--merge-cadence", type=int, default=3,
                   help="attempt a system-aware merge every Nth accept")
    p.add_argument("--gate-mode", default="auto",
                   help="auto = let the engine pick the paired gate (recommended; candidate & current share val tasks); or significant|paired|strict|threshold")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--store", default="git", help="git|copy|command")
    p.add_argument("--store-commit-cmd", default=None)
    p.add_argument("--no-regression", action="store_true",
                   help="reject candidates that break a previously-passing val task")
    p.add_argument("--resume", action="store_true",
                   help="reconstruct the pool/frontier from the run dir and continue the "
                        "search instead of restarting from the seed")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    store = make_store({"store": args.store, "store_commit_cmd": args.store_commit_cmd}, run_dir.root)
    adapter = load_adapter(Path(args.project))
    optimizer = harness.optimizer_from_command(shlex.split(args.optimizer))
    seed_val = SplitResult.from_dict(
        json.loads((run_dir.root / "baseline.json").read_text())["val"])

    result = gepa.gepa_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, seed_val=seed_val,
        max_metric_calls=args.max_metric_calls, max_iterations=args.max_iterations,
        minibatch_size=args.minibatch_size, n_trials=args.n_trials,
        component_selector=args.component_selector,
        selection_strategy=args.selection_strategy,
        max_merges=args.max_merges, merge_cadence=args.merge_cadence,
        gate_kwargs=({"k_se": args.k_se} if args.gate_mode == "auto"
                     else {"mode": args.gate_mode, "k_se": args.k_se}),
        no_regression=args.no_regression, seed=args.seed, store=store,
        resume=args.resume,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
