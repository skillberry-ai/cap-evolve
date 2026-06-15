"""gate — apply the acceptance decision (always on val) and print it.

A thin, inspectable front-end to ``agent_capo.gate.decide``. Algorithms call
the gate internally via the harness; this skill exists so an agent or a human can
reproduce/inspect a single accept/reject decision and understand the rule.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

from agent_capo.gate import decide


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gate")
    p.add_argument("--current", type=float, required=True, help="current best val reward")
    p.add_argument("--candidate", type=float, required=True, help="candidate val reward")
    p.add_argument("--mode", default="significant",
                   choices=["significant", "strict", "threshold", "simplicity_tiebreak"])
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--candidate-stderr", type=float, default=0.0)
    p.add_argument("--current-stderr", type=float, default=0.0)
    p.add_argument("--threshold", type=float, default=0.0)
    args = p.parse_args(argv)

    d = decide(
        args.current, args.candidate, split="val", mode=args.mode, k_se=args.k_se,
        candidate_stderr=args.candidate_stderr, current_stderr=args.current_stderr,
        threshold=args.threshold,
    )
    print(json.dumps(d.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
