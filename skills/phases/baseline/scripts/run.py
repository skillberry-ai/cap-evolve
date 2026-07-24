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
    p.add_argument("--reuse-baseline", default=None,
                   help="prior run dir: reuse its splits/baseline/seed/val-rollouts and "
                        "SKIP the baseline eval (algorithm starts at iter 1 on it)")
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--stall", type=int, default=0)
    p.add_argument("--max-metric-calls", type=int, default=0, help="0 = unlimited")
    p.add_argument("--max-usd", type=float, default=0.0,
                   help="0 = unlimited; total spend cap (runner + optimizer + intake)")
    p.add_argument("--max-optimizer-usd", type=float, default=0.0,
                   help="0 = off; separate cap on optimizer spend alone")
    p.add_argument("--run-ts", default=None, help="fixed timestamp for reproducible run dirs")
    p.add_argument("--resume", action="store_true",
                   help="reopen an existing run dir instead of failing; skip the baseline "
                        "eval when it already ran (baseline.json present)")
    args = p.parse_args(argv)

    Path(args.base).mkdir(parents=True, exist_ok=True)
    budget = Budget(max_iterations=args.max_iterations, stall=args.stall,
                    max_metric_calls=args.max_metric_calls, max_usd=args.max_usd,
                    max_optimizer_usd=args.max_optimizer_usd)
    run_dir = RunDir.create(Path(args.base), ts=args.run_ts, budget=budget, exist_ok=args.resume)

    # Resume fast-path: baseline already ran → the split is frozen, the seed is scored,
    # best_id is set. Re-print the recorded baseline and skip the (expensive) eval so the
    # algorithm resumes straight from the current best. state.json is left untouched.
    if args.resume and (run_dir.root / "baseline.json").exists():
        splits = run_dir.read_splits()
        recorded = json.loads((run_dir.root / "baseline.json").read_text(encoding="utf-8"))
        print(json.dumps({
            "run_dir": str(run_dir.root),
            "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
            "baseline_val": recorded.get("val", {}),
            "resumed": True,
        }, indent=2))
        return 0

    adapter = load_adapter(Path(args.project))

    # --reuse-baseline: copy a prior run's frozen split + baseline + seed snapshot +
    # seed val rollouts into this fresh run dir and SKIP the (expensive) baseline eval.
    if args.reuse_baseline:
        result = harness.reuse_baseline(Path(args.reuse_baseline), run_dir=run_dir)
        splits = run_dir.read_splits()
        print(json.dumps({
            "run_dir": str(run_dir.root),
            "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
            "baseline_val": result.to_dict(),
            "reused_baseline_from": str(args.reuse_baseline),
        }, indent=2))
        return 0

    ratios = tuple(float(x) for x in args.ratios.split(","))
    split_ids = None
    if args.split_ids:
        # Resolve the split-ids path robustly: as given (absolute or cwd-relative),
        # else relative to the project dir. `cap-evolve run` invokes baseline with
        # cwd=workdir, so a project-relative `split_ids_file: split_ids.json` in
        # capevolve.yaml would otherwise miss — this lets users author it naturally.
        sp = Path(args.split_ids)
        if not sp.exists():
            cand = Path(args.project) / args.split_ids
            if cand.exists():
                sp = cand
        split_ids = json.loads(sp.read_text(encoding="utf-8"))
    splits = harness.ensure_splits(adapter, run_dir, seed=args.seed, ratios=ratios,
                                   split_ids=split_ids)
    # Resolve the seed capability dir robustly: as given (absolute/cwd-relative),
    # else relative to the project dir. `cap-evolve run` invokes baseline with
    # cwd=workdir, so a project-relative `capability_path: seed_capability` in
    # capevolve.yaml would otherwise miss — let users author it naturally.
    cap_path = Path(args.capability)
    if not cap_path.exists():
        cand = Path(args.project) / args.capability
        if cand.exists():
            cap_path = cand
    result = harness.baseline(adapter, cap_path, run_dir=run_dir, n_trials=args.n_trials)

    print(json.dumps({
        "run_dir": str(run_dir.root),
        "splits": {"train": len(splits.train), "val": len(splits.val), "test": len(splits.test)},
        "baseline_val": result.to_dict(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
