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
from cap_evolve.gate import ParetoObjectiveError, decide
from cap_evolve.loop import has_valid_trials
from cap_evolve import objectives
from cap_evolve.specfile import spec_for_run

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


# The gate modes THIS script implements, and the single source of truth for them.
# `round.py` forwards its own --mode here verbatim, so it imports this list rather than
# repeating it: on run 33492876620 round 3 the two disagreed (round.py had no `choices=` at
# all), `--mode val` sailed through round.py, was rejected here, and emptied the entire
# round table while `eval_rc` stayed 0. Two copies of a list is how that happens.
#
# "pareto" (issue #665 ws3) and "epsilon_constraint" (issue #684 item 2) are BOTH also
# reachable natively through round.py (issue #684 item 1): round.py forwards --objectives/
# --metrics-*/--constraints here and, for pareto, additionally maintains a persistent
# cap_evolve.pareto_archive.ParetoArchive across rounds — see round.py's own docstring.
GATE_MODES = ["paired", "significant", "strict", "threshold", "pareto", "epsilon_constraint",
              "reward_gated"]


def _frozen_coverage(run_dir, per_task, split: str = "val") -> float:
    """Real coverage against the FROZEN split, not just the tasks a rollout exists for.

    ``SplitResult.coverage`` is ``n_scored / n_tasks`` where ``n_tasks`` counts only
    tasks that have a rollout file under this tag — reconstructed purely from disk
    (``harness.split_result_from_rollouts``). A candidate evaluated on a SUBSET of val
    (deliberately via ``--ids``, or by an eval that died partway through) therefore
    reads back ``coverage == 1.0``: every task it DID measure, it measured. That is
    exactly the blind spot ``gate.decide``'s low-coverage guard exists to catch, and it
    cannot see through it unless coverage is computed against the split cap-evolve
    actually froze, not against whatever happened to land on disk.
    """
    frozen = {str(i) for i in (run_dir.read_splits().ids(split) or [])}
    if not frozen:
        return 1.0
    scored = {str(pt.get("task_id")) for pt in (per_task or []) if has_valid_trials(pt)}
    return len(scored & frozen) / len(frozen)


def build_parser() -> argparse.ArgumentParser:
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
    p.add_argument("--mode", default="paired", choices=GATE_MODES)
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--veto-regressions", action="store_true",
                   help="ALSO reject a gate-passing candidate that drops any val task the parent "
                        "measured-and-passed. OFF by default — see regressions() for why.")
    p.add_argument("--allow-regression", action="store_true",
                   help="deprecated no-op: regressions no longer veto unless --veto-regressions")
    p.add_argument("--objectives", default=None,
                   help="--mode pareto only: JSON list of {name, direction}, e.g. "
                        '\'[{"name":"reward","direction":"maximize"},'
                        '{"name":"cost","direction":"minimize"}]\'. Default (omitted) = '
                        "reward maximize + cost minimize, with cap_evolve.gate's own "
                        "cost->latency->tokens fallback. Mirror capevolve.yaml's `objectives:` "
                        "block when the project declares one.")
    p.add_argument("--metrics-candidate", default=None,
                   help="--mode pareto only: JSON dict of the candidate's non-reward objective "
                        "values, e.g. '{\"cost\": 0.42}'. You source this yourself (e.g. the "
                        "evaluate phase's own cost_usd, or multirep.py's pooled cost across "
                        "independently-seeded blocks) — gate_check.py has no automatic "
                        "per-candidate cost aggregator.")
    p.add_argument("--metrics-current", default=None,
                   help="--mode pareto only: same shape as --metrics-candidate, for the "
                        "reference (--current) side.")
    p.add_argument("--metrics-stderr-candidate", default=None,
                   help="--mode pareto only: JSON dict of the SAME keys as --metrics-candidate, "
                        "each value its measured standard error. Required for every non-reward "
                        "objective — pareto mode refuses to fall back to a float-noise epsilon "
                        "(cap_evolve.gate.ParetoObjectiveError).")
    p.add_argument("--metrics-stderr-current", default=None,
                   help="--mode pareto only: same shape as --metrics-stderr-candidate, for the "
                        "reference (--current) side.")
    p.add_argument("--constraints", default=None,
                   help="--mode epsilon_constraint only: JSON list of {name, max}, e.g. "
                        '\'[{"name":"cost","max":1.0}]\' — Haimes et al. 1971 bounded-objective-'
                        "function method: maximize reward subject to each named metric staying "
                        "under its ceiling. Mirror capevolve.yaml's `constraints:` block. Needs "
                        "--metrics-candidate/--metrics-stderr-candidate for every constrained "
                        "name, same as --mode pareto's non-reward objectives.")
    return p


def _json_arg(raw: str | None, flag: str):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(json.dumps({"error": f"{flag} is not valid JSON: {exc}"}, indent=2))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    cur_tags = harness.parse_tags(args.current) \
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

    # Real coverage against the frozen split (see `_frozen_coverage`), min of both sides —
    # a candidate OR a reference measured on a subset is equally invalid to gate on.
    cand_frozen_cov = _frozen_coverage(run_dir, cand.per_task, "val")
    cur_frozen_cov = _frozen_coverage(run_dir, cur.per_task, "val")
    frozen_coverage = min(cand_frozen_cov, cur_frozen_cov)
    frozen_ids = {str(i) for i in (run_dir.read_splits().ids("val") or [])}
    cand_ids = {str(pt.get("task_id")) for pt in (cand.per_task or []) if has_valid_trials(pt)}
    missing_from_frozen_val = sorted(frozen_ids - cand_ids)

    deltas = harness._paired_deltas(cur, cand, footprint=fp)
    # Only when restricted: on a small footprint the zero-padded vector's cross-task spread
    # understates the real uncertainty, so floor it with per-task trial noise. Unrestricted
    # vectors keep the SE they always had.
    se_floor = (harness.paired_se_floor(run_dir, args.candidate, cur_tags[0], fp, len(deltas))
                if fp is not None and deltas else 0.0)
    # #711 reward_gated: per-trial records (cost lives per trial, not in SplitResult) + the
    # `optimizer.ablation.cost_gating` switch (false => decide() falls back to the legacy mode).
    rg = {}
    if args.mode == "reward_gated":
        spec = spec_for_run(run_dir)
        rg = dict(task_records=(objectives.load_trials(run_dir, cur_tags),
                                objectives.load_trials(run_dir, args.candidate)),
                  reward_gated_cfg=objectives.cfg_from_spec(spec),
                  cost_gating=objectives.cost_gating_enabled(spec))
    try:
        d = decide(cur.reward, cand.reward, split="val", mode=args.mode, k_se=args.k_se,
                   candidate_stderr=cand.stderr, current_stderr=cur.stderr,
                   threshold=args.threshold, paired_deltas=deltas,
                   paired_se_floor=se_floor, coverage=frozen_coverage, run_dir=run_dir,
                   objectives=_json_arg(args.objectives, "--objectives"),
                   metrics_candidate=_json_arg(args.metrics_candidate, "--metrics-candidate"),
                   metrics_current=_json_arg(args.metrics_current, "--metrics-current"),
                   metrics_stderr_candidate=_json_arg(
                       args.metrics_stderr_candidate, "--metrics-stderr-candidate"),
                   metrics_stderr_current=_json_arg(
                       args.metrics_stderr_current, "--metrics-stderr-current"),
                   constraints=_json_arg(args.constraints, "--constraints"), **rg)
    except (ParetoObjectiveError, ValueError) as exc:
        if not isinstance(exc, ParetoObjectiveError) and args.mode != "reward_gated":
            raise
        # Refuse the same way the rest of this script refuses an unjudgeable candidate
        # (no --current, no rollouts): a clean JSON error on stdout, rc 2 — never a
        # traceback, and never a verdict gate.py did not actually reach.
        print(json.dumps({"error": f"pareto gate: {exc}"}, indent=2))
        return 2

    regs = regressions(cur, cand)
    # The full COMPOSITION of the change, from the framework's shared classifier: what this
    # candidate broke AND what it fixed. ``regressions`` above is only the broke half, and it
    # exists to feed the veto; ``movement`` is what gets RECORDED, so a round table and a step
    # record can say what an accepted candidate traded. `r3_decide` (run 36175707483) was booked
    # accept with "BROKE vs both controls [33722]" living only in the agent's prose.
    mv = harness.movement(cur.per_task, cand.per_task)
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
                      "stderr": cand.stderr, "coverage": cand.coverage,
                      "coverage_of_frozen_val": round(frozen_coverage, 4),
                      "missing_from_frozen_val": missing_from_frozen_val},
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
        # broke/fixed/unresolved over the whole val split, so the trade-off is a NUMBER a
        # driver has to look at rather than something it may mention. `broke` is `regressions`
        # by construction (same shared rule); `fixed` is the half that was never reported, and
        # without it "it broke task X" reads as pure loss even when the edit fixed four others.
        "movement": {k: mv[k] for k in ("broke", "fixed", "unresolved")},
        "n_broke": len(mv["broke"]),
        "n_fixed": len(mv["fixed"]),
        "verdict": verdict,
        "directionally_positive_but_inconclusive": directionally_positive_but_inconclusive,
        "next": next_cmd,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
