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


# The pasted list and the two means must describe the SAME comparison: mean(Δ) is
# candidate − current by construction. Cross-checking them is the only length check
# possible here (the script never sees the val split), and it catches a truncated
# paste, a wrong-order paste, and flipped signs at once — each of which would
# otherwise print a confident accept/reject for an n the run never used.
# ponytail: 1e-4, not 1e-6, so means copied at the 4dp the dashboard prints still
# pass; truncation/mis-paste errors are orders of magnitude larger than that.
_DELTA_TOL = 1e-4


def parse_paired_deltas(raw: str, current: float, candidate: float, error):
    """Parse --paired-deltas, or call ``error`` (argparse: exit 2) with a fix."""
    fields = [x.strip() for x in raw.split(",") if x.strip()]
    if not fields:
        return None
    try:
        deltas = [float(x) for x in fields]
    except ValueError as exc:
        error(f"--paired-deltas: {exc}. Expected comma-separated numbers "
              f"(e.g. 1,0,0,0,0), one per val task; got {raw!r}.")
    mean_d = sum(deltas) / len(deltas)
    if abs(mean_d - (candidate - current)) > _DELTA_TOL:
        error(
            f"--paired-deltas has {len(deltas)} value(s) whose mean is {mean_d:+.4f}, "
            f"but --candidate minus --current is {candidate - current:+.4f}. The deltas "
            "must be the per-task cand-curr over ALL val tasks used for those means "
            "(a truncated paste is the usual cause) — otherwise the decision reports a "
            "gain and an n the run never made."
        )
    return deltas


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
                        "for --mode paired; without them paired falls back to significant. "
                        "mean(deltas) must equal --candidate minus --current (that is what "
                        "'the same tasks both sides' means), so a truncated or mis-pasted "
                        "list is refused instead of silently gating on the wrong n")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--candidate-stderr", type=float, default=0.0)
    p.add_argument("--current-stderr", type=float, default=0.0)
    p.add_argument("--threshold", type=float, default=0.0)
    args = p.parse_args(argv)

    deltas = parse_paired_deltas(args.paired_deltas, args.current, args.candidate, p.error)
    d = decide(
        args.current, args.candidate, split="val", mode=args.mode, k_se=args.k_se,
        candidate_stderr=args.candidate_stderr, current_stderr=args.current_stderr,
        threshold=args.threshold, paired_deltas=deltas,
    )
    print(json.dumps(d.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
