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
``gate.decide``. It also REPORTS **regressions** — val tasks the parent measured and passed
that dropped — as diagnosis for the next round. They do not veto an accept unless you pass
``--veto-regressions``; see ``regressions()`` for the measured reason that default flipped.

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

from cap_evolve import RunDir, footprint, harness
from cap_evolve.gate import decide
from cap_evolve.loop import has_valid_trials

EPS = 1e-9


def regressions(current, candidate) -> list[str]:
    """Val tasks the current best measured-and-PASSED that got worse. REPORTED, not a veto.

    As of one long run this list is DIAGNOSIS ONLY — it no longer blocks an accept
    unless you pass ``--veto-regressions``. The veto was measured to be the dominant cause
    of four consecutive null results on a multi-turn tool-use benchmark:

      * it fires on a byte-identical copy of the seed 42.8% of the time at 5 trials
        (12.9% at 10) — see the table below, which is why no trial count rescues it at the
        val sizes this benchmark allows;
      * in run_agentoptv4 it vetoed BOTH candidates that passed the significance test
        (``cA_partial`` Delta-bar +0.0167 > bar 0.0134, vetoed on task 8; ``cB_becabin``
        +0.0167, vetoed on 8/32/40). Those were the run's only two positive signals.

    A per-task reward at n trials is an estimate with its own error bar, so "this one task
    dropped" is not evidence of harm at the sizes involved; the PAIRED test on the mean
    already accounts for per-task movement in both directions and is the statistically
    correct decision rule. Churn (fix 2 / break 2 at an identical mean) is correctly a
    non-accept under the paired test — it just fails for the right reason (no significant
    gain) instead of being vetoed after passing.

    The list stays in the output because it is the most actionable thing the next round
    reads: it names which part of a bundled edit to drop.

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

    And it converges FASTER than "any strict drop below 1.0", because the drop must clear
    ``2·SE`` of its own per-task measurement — the same bar ``harness._candidate_task_impact``
    applies, kept in sync by ``test_regression_gate``. Without it the list reported a task as
    regressed for a single flipped rollout out of ten: on run_finalrun6 the same "task 27"
    was reported against structurally unrelated candidates, one of them a docstring-only edit
    that cannot change behaviour, and the optimizer spent three rounds re-deriving that it was
    noise. At one trial every SE is 0, the bar collapses to ``EPS``, and the rule is
    unchanged.
    """
    cur = {pt["task_id"]: pt for pt in (current.per_task or []) if has_valid_trials(pt)}
    cand = {pt["task_id"]: pt for pt in (candidate.per_task or []) if has_valid_trials(pt)}

    def _dropped(t) -> bool:
        pr = cur[t].get("reward", 0.0) or 0.0
        cd = cand[t].get("reward", 0.0) or 0.0
        return pr >= 1.0 - EPS and cd < pr and harness.move_is_resolved(
            pr, cd, cur[t].get("stderr") or 0.0, cand[t].get("stderr") or 0.0)

    return sorted(t for t in cur if t in cand and _dropped(t))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gate_check")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--candidate", required=True, help="candidate tag (== its dir name)")
    p.add_argument("--current", default=None,
                   help="tag to compare against; default = the run's current best_id. Accepts a "
                        "COMMA-SEPARATED list, whose trials are POOLED per task into one "
                        "reference — the way a round's byte-identical null-control replicates "
                        "become a lower-variance estimate of the same parent for free, since "
                        "their rollouts are already on disk (see round.py's control_replicates).")
    p.add_argument("--no-footprint", action="store_true",
                   help="measure the delta across EVERY val task, including the ones the edit "
                        "cannot causally reach. Footprint restriction is on by default and is a "
                        "no-op whenever the edit's surface cannot be determined; see "
                        "cap_evolve.footprint for why the unrestricted vector buries real "
                        "effects in the noise of tasks the edit never touched.")
    p.add_argument("--mode", default="paired",
                   choices=["paired", "significant", "strict", "threshold"])
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--veto-regressions", action="store_true",
                   help="ALSO reject a gate-passing candidate that drops any val task the parent "
                        "measured-and-passed. OFF by default — see regressions() for why.")
    p.add_argument("--allow-regression", action="store_true",
                   help="deprecated no-op: regressions no longer veto unless --veto-regressions")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    cur_tags = [t.strip() for t in (args.current or "").split(",") if t.strip()] \
        or ([run_dir.best_id] if run_dir.best_id else [])
    if not cur_tags:
        print(json.dumps({"error": "no --current tag and no best_id in the run dir "
                                   "(has baseline run?)"}, indent=2))
        return 2
    cur_tag = ",".join(cur_tags)

    cur = harness.split_result_from_rollouts(run_dir, cur_tags, "val")
    cand = harness.split_result_from_rollouts(run_dir, args.candidate, "val")
    if not cand.per_task:
        print(json.dumps({"error": f"no val rollouts for tag {args.candidate!r} — run the "
                                   "evaluate phase on FULL val first"}, indent=2))
        return 2

    # Which val tasks the edit can causally reach. The candidate snapshot is diffed against
    # the FIRST reference tag's snapshot: a pooled reference is several byte-identical copies
    # of one parent, so any of them gives the same diff. None when it cannot be determined,
    # which leaves the full-vector behaviour exactly as it was.
    fp = None
    if not args.no_footprint:
        fp = footprint.footprint(
            run_dir, parent_dir=run_dir.candidate_dir(cur_tags[0]),
            cand_dir=run_dir.candidate_dir(args.candidate),
            tags=[*cur_tags, args.candidate], split="val",
            all_task_ids=[pt.get("task_id") for pt in (cand.per_task or [])])

    deltas = harness._paired_deltas(cur, cand, footprint=fp)
    # Only when restricted: on a small footprint the zero-padded vector's cross-task spread
    # understates the real uncertainty, so floor it with per-task trial noise. Unrestricted
    # vectors keep the SE they always had.
    se_floor = (harness.paired_se_floor(run_dir, args.candidate, cur_tags[0], fp, len(deltas))
                if fp is not None and deltas else 0.0)
    d = decide(cur.reward, cand.reward, split="val", mode=args.mode, k_se=args.k_se,
               candidate_stderr=cand.stderr, current_stderr=cur.stderr,
               threshold=args.threshold, paired_deltas=deltas,
               paired_se_floor=se_floor, coverage=cand.coverage, run_dir=run_dir)

    regs = regressions(cur, cand)
    accept = bool(d.accept) and not (regs and args.veto_regressions)
    verdict = "indecisive" if d.indecisive else ("accept" if accept else "reject")
    # A reject with delta > 0 is not the same as a reject with delta <= 0: the first is
    # a positive direction the gate could not yet resolve at this n, and growing n on
    # this SAME candidate (never a new edit) may resolve it — see references/algorithm.md,
    # "Provisional candidates". Surfaced here so the driver notices it without having to
    # compute delta > 0 itself.
    # Off `d.accept`, not the regression-vetoed `accept`: a candidate the GATE accepted and
    # `--veto-regressions` then rejected has nothing left for more trials to resolve — the
    # veto is a per-task harm call, not a measurement-power problem.
    directionally_positive_but_inconclusive = (
        not d.indecisive and not d.accept and d.delta > 0)
    next_cmd = f"scripts/commit.py --decision {'accept' if accept else 'reject'}"
    if directionally_positive_but_inconclusive:
        next_cmd += " (or --decision provisional, then scripts/grow.py, to buy more n on this candidate)"
    print(json.dumps({
        "current": {"tag": cur_tag, "reward": cur.reward, "stderr": cur.stderr,
                    "pooled_tags": cur_tags if len(cur_tags) > 1 else None},
        "candidate": {"tag": args.candidate, "reward": cand.reward,
                      "stderr": cand.stderr, "coverage": cand.coverage},
        "gate": d.to_dict(),
        "paired_n": len(deltas or []),
        # What the delta was measured over. `restricted: false` means the edit's surface could
        # not be determined, so every val task is in the vector and the SE carries the noise of
        # tasks the edit cannot reach — read the verdict knowing that.
        "footprint": ({"restricted": True, "n_in_footprint": len(fp),
                       "n_tasks": len(cand.per_task or []), "tasks": sorted(map(str, fp)),
                       "paired_se_floor": round(se_floor, 6),
                       "reading": "tasks OUTSIDE this set entered the delta vector as 0.0 (an "
                                  "edit that cannot reach a task has no effect on it by "
                                  "construction), so the SE reflects only the tasks in play — "
                                  "floored by `paired_se_floor`, the SE those tasks' own "
                                  "per-trial noise implies, so a handful of one-rollout flips "
                                  "cannot read as a significant mean"}
                      if fp is not None else
                      {"restricted": False,
                       "reading": ("disabled by --no-footprint" if args.no_footprint else
                                   "the edit's surface could not be localized (no diff, a "
                                   "rewrite-sized diff, no rollouts, or it reaches every "
                                   "task) — full-vector measurement, as before")}),
        "regressions": regs,
        "verdict": verdict,
        "directionally_positive_but_inconclusive": directionally_positive_but_inconclusive,
        "next": next_cmd,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
