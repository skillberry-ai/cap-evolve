"""gepa-reflective — GEPA-style reflective Pareto evolution.

Selects a parent from the per-task Pareto frontier (keeping specialists), builds a
reflective dataset over the parent's failing val tasks, proposes an edit, and
accepts on the val significance gate. Thin wrapper over ``harness.pareto_loop``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from agent_capo import RunDir, harness
from agent_capo.store import make_store
from agent_capo.check import load_adapter
from agent_capo.loop import SplitResult

FOCUS = "pareto"
ALGO = "gepa-reflective"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=ALGO)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--optimizer", required=True, help="optimizer cmd with {workdir} {prompt}")
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--gate-mode", default="significant")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--store", default="git", help="git|copy|command")
    p.add_argument("--store-commit-cmd", default=None)
    p.add_argument("--no-regression", action="store_true")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    store = make_store({"store": args.store, "store_commit_cmd": args.store_commit_cmd}, run_dir.root)
    adapter = load_adapter(Path(args.project))
    optimizer = harness.optimizer_from_command(shlex.split(args.optimizer))
    seed_val = SplitResult.from_dict(
        json.loads((run_dir.root / "baseline.json").read_text())["val"])

    result = harness.pareto_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, seed_val=seed_val,
        max_iterations=args.max_iterations, n_trials=args.n_trials,
        gate_kwargs={"mode": args.gate_mode, "k_se": args.k_se}, no_regression=args.no_regression, store=store,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
