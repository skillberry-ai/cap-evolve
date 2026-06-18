"""baseline — create the run dir, freeze the splits, score the seed on val.

This establishes the starting point every algorithm compares against. It is the
first step that touches data, so it owns split creation (seeded, written once).
Prints the run-dir path and the baseline val score as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Budget, RunDir, harness
from cap_evolve.check import load_adapter


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="baseline")
    p.add_argument("--base", default=".capevolve", help="dir under which run_* is created")
    p.add_argument("--project", required=True, help="dir with adapters/adapter.py")
    p.add_argument("--capability", required=True, help="seed capability dir")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--ratios", default="0.5,0.25,0.25")
    p.add_argument("--split-ids", default=None,
                   help="JSON file {train:[],val:[],test:[]} to pin the split explicitly")
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--stall", type=int, default=0)
    p.add_argument("--max-metric-calls", type=int, default=0, help="0 = unlimited")
    p.add_argument("--max-usd", type=float, default=0.0,
                   help="0 = unlimited; total spend cap (runner + optimizer + intake)")
    p.add_argument("--max-optimizer-usd", type=float, default=0.0,
                   help="0 = off; separate cap on optimizer spend alone")
    p.add_argument("--run-ts", default=None, help="fixed timestamp for reproducible run dirs")
    args = p.parse_args(argv)

    Path(args.base).mkdir(parents=True, exist_ok=True)
    budget = Budget(max_iterations=args.max_iterations, stall=args.stall,
                    max_metric_calls=args.max_metric_calls, max_usd=args.max_usd,
                    max_optimizer_usd=args.max_optimizer_usd)
    run_dir = RunDir.create(Path(args.base), ts=args.run_ts, budget=budget)

    adapter = load_adapter(Path(args.project))
    ratios = tuple(float(x) for x in args.ratios.split(","))
    split_ids = None
    if args.split_ids:
        split_ids = json.loads(Path(args.split_ids).read_text(encoding="utf-8"))
    splits = harness.ensure_splits(adapter, run_dir, seed=args.seed, ratios=ratios,
                                   split_ids=split_ids)
    result = harness.baseline(adapter, Path(args.capability), run_dir=run_dir, n_trials=args.n_trials)

    print(json.dumps({
        "run_dir": str(run_dir.root),
        "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
        "baseline_val": result.to_dict(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
