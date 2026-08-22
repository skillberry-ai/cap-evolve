"""gate — apply the acceptance decision (always on val) and print it.

A thin, inspectable front-end to ``cap_evolve.gate.decide``. Algorithms call
the gate internally via the harness; this skill exists so an agent or a human can
reproduce/inspect a single accept/reject decision and understand the rule.

Two ways to call it:

**Scalar mode** — pass ``--current``/``--candidate`` (plus optional stderrs). This is
the unpaired significance test. It cannot express ``--mode paired``: a paired test
needs the per-task delta vector, which two scalar means do not carry.

**Rollout mode** — pass ``--run-dir --current-tag --candidate-tag``. Both sides'
``SplitResult``s are rebuilt from the persisted val rollouts, so the aligned per-task
deltas exist and ``--mode paired`` becomes reachable. This is the same gate the
deterministic loops apply (``harness.run_step`` defaults to ``paired`` whenever the
per-task data aligns), computed by the same helpers — so a human or an agent-mode
loop inspecting a decision here gets the *real* rule, not a weaker stand-in.

Prefer rollout mode whenever the rollouts exist. ``paired`` is strictly more powerful
than ``significant`` on the same data because it removes per-task difficulty variance.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

from cap_evolve.gate import decide

_MODES = ["paired", "significant", "strict", "threshold"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gate")
    p.add_argument("--current", type=float, help="current best val reward (scalar mode)")
    p.add_argument("--candidate", type=float, help="candidate val reward (scalar mode)")
    p.add_argument("--mode", default="significant", choices=_MODES)
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--candidate-stderr", type=float, default=0.0)
    p.add_argument("--current-stderr", type=float, default=0.0)
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--run-dir", help="run dir (rollout mode: enables --mode paired)")
    p.add_argument("--current-tag", help="candidate id/tag of the current best")
    p.add_argument("--candidate-tag", help="candidate id/tag of the challenger")
    args = p.parse_args(argv)

    kw: dict = {}
    current, candidate = args.current, args.candidate
    cur_se, cand_se = args.current_stderr, args.candidate_stderr

    tags = (args.run_dir, args.current_tag, args.candidate_tag)
    if any(tags):
        if not all(tags):
            p.error("rollout mode needs --run-dir AND --current-tag AND --candidate-tag")
        from cap_evolve import RunDir
        from cap_evolve.harness import _paired_deltas, split_result_from_rollouts
        rd = RunDir.open(args.run_dir)
        cur = split_result_from_rollouts(rd, args.current_tag, "val")
        cand = split_result_from_rollouts(rd, args.candidate_tag, "val")
        # Rollouts are the source of truth here; explicit scalars would let a stale
        # number silently disagree with the deltas computed from the same files.
        current, cur_se = cur.reward, cur.stderr
        candidate, cand_se = cand.reward, cand.stderr
        kw["coverage"] = cand.coverage
        kw["run_dir"] = rd
        deltas = _paired_deltas(cur, cand)
        if deltas:
            kw["paired_deltas"] = deltas
        elif args.mode == "paired":
            # Say so instead of letting decide() quietly downgrade to `significant`.
            print(json.dumps({
                "error": "no aligned per-task val data for a paired test",
                "fix": "check both tags have val rollouts with valid trials "
                       "(tasks unscored on either side are dropped from the pairing)",
                "current_tag": args.current_tag, "candidate_tag": args.candidate_tag,
            }, indent=2))
            return 2
    elif current is None or candidate is None:
        p.error("scalar mode needs --current and --candidate "
                "(or use rollout mode: --run-dir --current-tag --candidate-tag)")
    elif args.mode == "paired":
        p.error("--mode paired needs per-task data: pass "
                "--run-dir --current-tag --candidate-tag instead of scalar means")

    d = decide(
        current, candidate, split="val", mode=args.mode, k_se=args.k_se,
        candidate_stderr=cand_se, current_stderr=cur_se,
        threshold=args.threshold, **kw,
    )
    out = d.to_dict()
    # Only report the pair count when the paired test actually ran — printing it for
    # `significant` would imply the decision used pairing when decide() ignored it.
    if args.mode == "paired" and "paired_deltas" in kw:
        out["paired_n"] = len(kw["paired_deltas"])
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
