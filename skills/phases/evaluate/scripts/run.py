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
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    adapter = load_adapter(Path(args.project))
    cand = Path(args.candidate)
    cand_dir = cand if cand.exists() else run_dir.candidate_dir(args.candidate)
    result = harness.evaluate_candidate(adapter, cand_dir, run_dir=run_dir,
                                        split=args.split, n_trials=args.n_trials,
                                        tag=cand_dir.name)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
