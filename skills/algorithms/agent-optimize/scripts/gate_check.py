"""gate_check — the honest accept/reject decision for agent-optimize, from real rollouts.

Why this exists instead of ``phases/gate/scripts/run.py``: that CLI takes only two
scalar means, so it can reach the *unpaired* ``significant`` test and nothing else.
The deterministic loops all default to the **paired** gate (mean per-task Δ vs the SE
of those deltas), which needs the aligned per-task vector — data the scalar CLI has no
way to accept. So the agent had no reachable path to the same gate the rest of
cap-evolve uses.

This script closes that: it reconstructs both sides' ``SplitResult`` from the persisted
val rollouts (``harness.split_result_from_rollouts``), builds the paired delta vector
with the SAME helper the loops use (``harness._paired_deltas``), and calls the SAME
``gate.decide``. It also applies **no-regression** — reject a mean gain that strictly
drops any val task the parent measured and passed — which was previously prose only.

Tags are candidate dir names: the evaluate phase writes rollouts as
``<task>__<tag>__t<k>.json`` with ``tag = candidate_dir.name``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Imported for its side effect ONLY: seeds sys.path so `cap_evolve` resolves when
# this script is run standalone (`python <this-file>`). Must precede the
# cap_evolve imports below; not "unused" — deleting it breaks standalone runs.
import _bootstrap  # noqa: F401  # side-effect import, see above

from cap_evolve import RunDir, harness
from cap_evolve.gate import decide
from cap_evolve.loop import has_valid_trials

EPS = 1e-9


def regressions(current, candidate) -> list[str]:
    """Val tasks the current best measured-and-PASSED that got worse.

    Mirrors ``harness._movement`` exactly -- the parent must have scored a full 1.0
    (``par >= 1.0 - EPS``), which is what SKILL.md means by "measured-and-passed".
    Tasks with no valid trial on either side are missing data, not evidence, so an
    infra outage can't veto a genuinely better candidate.

    This USED to veto on any strict drop from any parent level, which silently made
    agent-optimize's gate stricter than every other algorithm's -- and uniquely
    broken at num_trials > 1. At 1 trial rewards are 0/1 so the two rules coincide.
    Above that, a per-task reward is a fraction and the parent's is frozen from one
    draw, so a task whose true rate is 0.45 but which drew 4/5 vetoes almost any
    re-measurement of the SAME capability. Measured on the v4 val rates,
    P(veto fires on a byte-identical seed copy):

        trials   any-drop (old)   parent-passed (this rule, == harness)
             1            0.889                                  0.889
             5            0.983                                  0.428
            10            0.990                                  0.129

    The old rule got WORSE as trials rose, so no trial count could fix it; the
    harness rule converges, which is the behaviour a variance-aware gate must have.
    """
    cur = {pt["task_id"]: pt.get("reward", 0.0) for pt in (current.per_task or [])
           if has_valid_trials(pt)}
    cand = {pt["task_id"]: pt.get("reward", 0.0) for pt in (candidate.per_task or [])
            if has_valid_trials(pt)}
    return sorted(t for t, pr in cur.items()
                  if t in cand and pr >= 1.0 - EPS and cand[t] < pr - EPS)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gate_check")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--candidate", required=True, help="candidate tag (== its dir name)")
    p.add_argument("--current", default=None,
                   help="tag to compare against; default = the run's current best_id")
    p.add_argument("--mode", default="paired",
                   choices=["paired", "significant", "strict", "threshold",
                            "simplicity_tiebreak"])
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--allow-regression", action="store_true",
                   help="skip the no-regression veto (NOT recommended; audit only)")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    cur_tag = args.current or run_dir.best_id
    if not cur_tag:
        print(json.dumps({"error": "no --current tag and no best_id in the run dir "
                                   "(has baseline run?)"}, indent=2))
        return 2

    cur = harness.split_result_from_rollouts(run_dir, cur_tag, "val")
    cand = harness.split_result_from_rollouts(run_dir, args.candidate, "val")
    if not cand.per_task:
        print(json.dumps({"error": f"no val rollouts for tag {args.candidate!r} — run the "
                                   "evaluate phase on FULL val first"}, indent=2))
        return 2

    deltas = harness._paired_deltas(cur, cand)
    d = decide(cur.reward, cand.reward, split="val", mode=args.mode, k_se=args.k_se,
               candidate_stderr=cand.stderr, current_stderr=cur.stderr,
               threshold=args.threshold, paired_deltas=deltas,
               coverage=cand.coverage, run_dir=run_dir)

    regs = [] if args.allow_regression else regressions(cur, cand)
    accept = bool(d.accept) and not regs
    verdict = "indecisive" if d.indecisive else ("accept" if accept else "reject")
    print(json.dumps({
        "current": {"tag": cur_tag, "reward": cur.reward, "stderr": cur.stderr},
        "candidate": {"tag": args.candidate, "reward": cand.reward,
                      "stderr": cand.stderr, "coverage": cand.coverage},
        "gate": d.to_dict(),
        "paired_n": len(deltas or []),
        "regressions": regs,
        "verdict": verdict,
        "next": (f"scripts/commit.py --decision {'accept' if accept else 'reject'}"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
