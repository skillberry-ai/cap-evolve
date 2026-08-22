"""evaluate — score a candidate on a split with multi-trial honesty + pass^k.

Thin wrapper over the shared harness so any host can evaluate by parsing the JSON
on stdout. Never scores the test split (that is finalize's sealed job).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="evaluate")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--candidate", required=True, help="candidate id or dir to evaluate")
    p.add_argument("--split", default="val", choices=["train", "val"])
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--ks", default=None,
                   help="comma-separated k values for pass^k/pass@k "
                        "(default: 1..n-trials, so the k you paid for is reported)")
    args = p.parse_args(argv)

    # ks defaults to every k the trials can support. The harness default is (1, 2),
    # which silently drops pass^3 from a --n-trials 3 run — the exact reliability
    # figure the extra trial was bought for. A k above a task's trial count is
    # omitted by aggregate_scores, so over-wide ks is safe, never a misleading 0.0.
    ks = (tuple(int(x) for x in args.ks.split(",") if x.strip()) if args.ks
          else tuple(range(1, max(1, args.n_trials) + 1)))

    if args.n_trials <= 1:
        # Loud and auditable rather than a silently falsely-confident number: with one
        # trial every per-task stderr is 0, so the combined SE is between-task only and
        # pass^k is undefined beyond k=1. Same posture as gate._warn_se_zero.
        print("evaluate: --n-trials=1 — within-task variance is unmeasured (per-task "
              "stderr=0) and pass^k is only defined at k=1. Honest only for a "
              "deterministic target; pass --n-trials 3+ for a stochastic one.",
              file=sys.stderr)

    run_dir = RunDir.open(Path(args.run_dir))
    adapter = load_adapter(Path(args.project))
    cand = Path(args.candidate)
    cand_dir = cand if cand.exists() else run_dir.candidate_dir(args.candidate)
    result = harness.evaluate_candidate(adapter, cand_dir, run_dir=run_dir,
                                        split=args.split, n_trials=args.n_trials,
                                        ks=ks, tag=cand_dir.name)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
