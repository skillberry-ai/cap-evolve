"""finalize — score the best candidate on the SEALED test split, exactly once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from agent_capo import RunDir, harness
from agent_capo.check import load_adapter


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="finalize")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--n-trials", type=int, default=1)
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    adapter = load_adapter(Path(args.project))
    best_dir = run_dir.candidate_dir(run_dir.best_id)
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir, n_trials=args.n_trials)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
