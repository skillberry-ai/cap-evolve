"""gate — apply the acceptance decision (always on val) and print it.

A thin, inspectable front-end to ``cap_evolve.gate.decide``. Algorithms call
the gate internally via the harness; this skill exists so an agent or a human can
reproduce/inspect a single accept/reject decision and understand the rule.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

from cap_evolve.gate import decide


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gate")
    p.add_argument("--current", type=float, required=True, help="current best val reward")
    p.add_argument("--candidate", type=float, required=True, help="candidate val reward")
    p.add_argument("--mode", default="significant",
                   choices=["paired", "significant", "strict", "threshold", "simplicity_tiebreak"],
                   help="paired is the default in real runs (the harness pairs per-task val "
                        "rewards itself). This standalone front-end defaults to significant "
                        "because it takes means+SEs, not per-task data; pass --paired-deltas "
                        "to reproduce a paired decision.")
    p.add_argument("--paired-deltas", default="",
                   help="comma-separated per-task deltas (cand-curr over the SAME val tasks) "
                        "for --mode paired; without them paired falls back to significant")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--candidate-stderr", type=float, default=0.0)
    p.add_argument("--current-stderr", type=float, default=0.0)
    p.add_argument("--threshold", type=float, default=0.0)
    args = p.parse_args(argv)

    deltas = [float(x) for x in args.paired_deltas.split(",") if x.strip()] or None
    d = decide(
        args.current, args.candidate, split="val", mode=args.mode, k_se=args.k_se,
        candidate_stderr=args.candidate_stderr, current_stderr=args.current_stderr,
        threshold=args.threshold, paired_deltas=deltas,
    )
    print(json.dumps(d.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
