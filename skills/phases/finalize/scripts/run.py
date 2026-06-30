"""finalize — score the best candidate on the SEALED test split, exactly once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="finalize")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--n-trials", type=int, default=1)
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    adapter = load_adapter(Path(args.project))
    best_dir = run_dir.candidate_dir(run_dir.best_id)
    # Also score the unmodified seed (baseline) on the sealed test split, so the headline
    # is the honest optimized-vs-baseline improvement on held-out tasks. `baseline()` always
    # snapshots the seed, so a missing `candidates/seed` means a corrupted run dir — fail
    # fast rather than silently producing a misleading baseline==optimized comparison.
    seed_dir = run_dir.candidate_dir("seed")
    if not seed_dir.exists():
        raise FileNotFoundError(
            f"baseline 'seed' candidate not found at {seed_dir} — the run dir looks "
            "corrupted (baseline() should have snapshotted it). Refusing to finalize "
            "without a baseline to compare on the sealed test split."
        )
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir,
                               n_trials=args.n_trials, baseline_dir=seed_dir)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
