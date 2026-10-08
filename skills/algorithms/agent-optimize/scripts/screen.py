"""screen — cheap SUBSET triage on val. Kills bad candidates; can never accept one.

The economics this exists for: a full-val evaluation costs ``val_n × num_trials``
rollouts and is paid once per candidate per round. Most edits are not close calls, and
paying full val to discover that is the biggest waste in a run. So: screen the
candidate on a small, *deterministically chosen*, *informative* subset of val first,
kill it there if it is clearly harmful, and only promote survivors to the full-val
paired gate.

**The parent side of the comparison is free.** The current best already has full-val
rollouts on disk, so the screen re-reads its per-task rewards instead of re-running it.
Only the candidate pays, and only for the subset — that is where the saving comes from.

A promotion ladder, one call per rung (``--tier``):

    tier 1  ~25% of val, 1 trial   → kill obvious harm for a quarter of the price
    tier 2  ~50% of val, 1 trial   → a second look before paying full val
    (then)  FULL val × num_trials  → the evaluate phase + gate_check.py: the ONLY accept

Tier 2 does **not** re-run tier 1's tasks: the candidate's screen rollouts are merged
across every ``<tag>__screen*`` tag, so each rung only pays for the ids it adds.

This script prints ``"decision": "kill" | "promote"``. It never prints ``accept`` and
carries no code path that could: acceptance is ``gate_check.py`` on FULL val (Δ̄ > k·SE
plus the no-regression veto), by construction and by honesty invariant 1.

Every screen is written to ``<run_dir>/screens/<tag>__tier<N>.json`` — subset ids, the
seed, the deltas, the decision, and the MEASURED rollout economics — so any kill is
reproducible and auditable after the fact.

**issue #684 item 5 — DELIBERATE BEHAVIOR CHANGE: kill is a gross-failure check, not a
significance test.** The old rule killed on ``mean(Δ) + k_se·SE < 0`` — i.e. required
the subset to clear its own statistical significance bar. Measured on a real run,
tier-1 subsets (5-11 tasks) had SEs of 0.11-0.17 while the round deltas that actually
mattered were 0.02-0.09: the screen's SE was ALWAYS bigger than the effect it needed to
resolve, so the rule could structurally never fire (0 kills across 7 candidates in that
run, 0/8 in an earlier one, while screening cost more rollouts than it saved). Per
GEPA's own validated design — its minibatch gate is a cheap "did it beat the parent on
this subset, yes or no", no significance test, because the EXPENSIVE full eval is the
real decision point — this script's kill rule is now ``mean(Δ) <= --gross-kill-
threshold`` (default ``-0.15``, see ``cap_evolve.subsample.GROSS_KILL_DELTA``),
regardless of SE. Promote is everything else. See ``references/measured-lessons.md``
and ``references/algorithm.md`` for the full economics writeup.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter
# TIER_FRAC (rung → fraction of val) and MIN_K (absolute subset floor) live in subsample.py so
# the baseline-time screening_economics (#631) prices exactly the rung this script fires.
from cap_evolve.subsample import (
    GROSS_KILL_DELTA, MIN_K, TIER_FRAC, full_val_ceiling, paired_deltas_on, screen_decision,
    screen_savings, select_screen_subset,
)


def _screen_tags(run_dir: RunDir, tag: str) -> list[str]:
    """Every ``<tag>__screenN`` tag that already has val rollouts on disk."""
    seen = set()
    for f in (run_dir.rollouts / "val").glob(f"*__{tag}__screen*__t*.json"):
        parts = f.name.split("__")
        # <task>__<tag…>__screenN__t<k>.json — the screen tag is everything before __t<k>
        seen.add("__".join(parts[1:-1]))
    return sorted(seen)


def _merged_per_task(run_dir: RunDir, tags: list[str]) -> list:
    """Union of per-task val records across tags (later tags win on a collision)."""
    out: dict = {}
    for tg in tags:
        for pt in harness.split_result_from_rollouts(run_dir, tg, "val").per_task or []:
            out[str(pt.get("task_id"))] = pt
    return list(out.values())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="screen")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--candidate", required=True, help="working-copy dir to screen")
    p.add_argument("--tag", default=None,
                   help="candidate tag; default = the candidate dir name")
    p.add_argument("--current", default=None,
                   help="parent tag to compare against; default = the run's best_id")
    p.add_argument("--tier", type=int, default=1, choices=sorted(TIER_FRAC),
                   help="promotion rung: 1 (~25%% of val) | 2 (~50%%) | 3 (~75%%)")
    p.add_argument("--k", type=int, default=0,
                   help="explicit subset size; overrides --tier's fraction")
    p.add_argument("--seed", type=int, default=None,
                   help="subset seed; default = the frozen splits seed + tier "
                        "(so each rung draws a different holdout, reproducibly)")
    p.add_argument("--holdout-frac", type=float, default=0.34,
                   help="fraction of the subset drawn at random from tasks the parent "
                        "PASSES, so the screen can see a regression (default 0.34)")
    p.add_argument("--k-se", type=float, default=1.0,
                   help="vestigial since #684 item 5 (kill no longer requires "
                        "significance) — accepted for backward-compatible call sites, "
                        "no longer affects the decision; see --gross-kill-threshold")
    p.add_argument("--gross-kill-threshold", type=float, default=GROSS_KILL_DELTA,
                   help="kill iff the subset's mean Δ is at or below this, REGARDLESS "
                        f"of SE (default {GROSS_KILL_DELTA}: above the ~0.10 drift "
                        "observed between byte-identical control replicates, below the "
                        "~0.2 observed on a confirmed gross failure — see "
                        "cap_evolve.subsample.GROSS_KILL_DELTA)")
    p.add_argument("--broken", default="",
                   help="comma-separated task ids a previous edit broke — screened first")
    p.add_argument("--ids", default="",
                   help="comma-separated val task ids to screen on, chosen by YOUR OWN method "
                        "(trajectory-similarity clustering, reading rollouts, anything) — "
                        "bypasses select_screen_subset's fixed broken/informative/holdout "
                        "heuristic entirely. --tier/--k/--broken/--holdout-frac are ignored "
                        "when this is set. The kill/promote decision and audit trail are "
                        "unchanged — this only changes WHICH tasks are screened, never "
                        "whether a screen can accept (it still can't).")
    p.add_argument("--rationale", default=None,
                   help="WHY this subset — which cluster/tasks the edit targets and what the "
                        "rest of the subset guards (#437). Recorded as subset.rationale in the "
                        "screen record and graph.jsonl; defaults to the selector's own note.")
    p.add_argument("--n-trials", type=int, default=1,
                   help="trials per screened task (1 is the point; >1 is not a gate)")
    p.add_argument("--workers", type=int, default=None,
                   help="concurrent rollouts (adapter must be thread-safe)")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    cand_dir = Path(args.candidate)
    if not cand_dir.is_dir():
        cand_dir = run_dir.candidate_dir(args.candidate)
    if not cand_dir.is_dir():
        print(json.dumps({"error": f"candidate dir not found: {args.candidate}"}, indent=2))
        return 2
    # Defensive: a workdir built by a bare `cp -r` (SKILL.md step 2's own documented pattern)
    # never gets LEDGER.md/JOURNAL.md/RUNMAP.md/PROCESS.md unless its source already had them
    # — this guarantees them regardless of how `cand_dir` came to exist.
    harness.ensure_framework_memory(cand_dir, run_dir)

    tag = args.tag or cand_dir.name
    cur_tag = args.current or run_dir.best_id
    if not cur_tag:
        print(json.dumps({"error": "no --current tag and no best_id (has baseline run?)"},
                         indent=2))
        return 2

    val_ids = run_dir.read_splits().ids("val")
    parent = harness.split_result_from_rollouts(run_dir, cur_tag, "val")
    if not parent.per_task:
        print(json.dumps({
            "error": f"no val rollouts for parent tag {cur_tag!r} — the screen reads the "
                     "parent's existing full-val rollouts (that is what makes it cheap)",
            "fix": "run the baseline / a full-val evaluate for the current best first",
        }, indent=2))
        return 2

    custom_ids = [i.strip() for i in (args.ids or "").split(",") if i.strip()]
    if custom_ids:
        val_id_set = {str(i) for i in val_ids}
        chosen = sorted({i for i in custom_ids if i in val_id_set})
        sub = {"ids": chosen, "broken": [], "holdout": [], "informative": chosen,
               "k": len(chosen), "requested_k": len(custom_ids), "seed": None,
               "holdout_frac": None, "pool_n": len(parent.per_task),
               "rationale": f"optimizer-chosen subset ({len(chosen)} of {len(custom_ids)} "
                            "requested ids fell inside the frozen val split), bypassing "
                            "select_screen_subset's heuristic"}
    else:
        frac = TIER_FRAC[args.tier]
        k = args.k or max(MIN_K, int(round(frac * len(val_ids))))
        seed = args.seed if args.seed is not None else int(run_dir.read_splits().seed) + args.tier
        broken = [b for b in (args.broken or "").split(",") if b.strip()]
        sub = select_screen_subset(parent.per_task, k=k, seed=seed,
                                   holdout_frac=args.holdout_frac,
                                   broken_ids=[b.strip() for b in broken])
    if args.rationale and args.rationale.strip():
        sub["rationale"] = args.rationale.strip()

    # Rungs are cumulative: never re-run a task an earlier rung already screened.
    prior_tags = _screen_tags(run_dir, tag)
    already = {str(pt.get("task_id")) for pt in _merged_per_task(run_dir, prior_tags)}
    new_ids = [i for i in sub["ids"] if i not in already]

    screen_tag = f"{tag}__screen{args.tier}"
    fired = 0
    screen_cost_usd = 0.0
    if new_ids:
        res = harness.evaluate_candidate(
            load_adapter(Path(args.project)), cand_dir, run_dir=run_dir,
            split="val", n_trials=max(1, args.n_trials), tag=screen_tag,
            workers=args.workers, ids=new_ids, ks=(1,))
        fired = len(new_ids) * max(1, args.n_trials)
        screen_cost_usd = res.cost_usd

    cand_per_task = _merged_per_task(run_dir, sorted({*prior_tags, screen_tag}))
    pair = paired_deltas_on(parent.per_task, cand_per_task, sub["ids"])
    decision = screen_decision(pair["deltas"], k_se=args.k_se,
                               regressed=pair["regressed"],
                               gross_kill_threshold=args.gross_kill_threshold)

    # ARITHMETIC kill. When the screened ids already cover every val task the parent
    # fails, the unscreened remainder is all tasks the parent passes, so it can only
    # stay level or regress — and the candidate's best conceivable full-val mean is
    # computable. If that ceiling cannot beat the parent, no full-val eval can ever
    # accept, and paying for one buys strictly nothing. This still cannot accept
    # anything: the only conclusion it can reach is "reject".
    ceiling = full_val_ceiling(parent.per_task, cand_per_task, sub["ids"],
                               [str(i) for i in val_ids])
    # STRICTLY negative only. A best-case Δ̄ of exactly 0.0 also cannot accept (the bar
    # is >= 0), but that is the degenerate "parent already perfect on the screened set"
    # case, and escalating it would override the deliberate promote-on-a-flat-subset
    # bias for no gain. Keep the bias; kill only when the ceiling is provably BELOW the
    # parent.
    if (ceiling.get("best_case_mean_delta") is not None
            and ceiling["best_case_mean_delta"] < -1e-9
            and decision["decision"] != "kill"):
        decision = {**decision, "decision": "kill", "provable": True,
                    "inconclusive": False,
                    "reason": "PROVABLE kill (not a statistical one): "
                              + ceiling["reason"]}

    savings = screen_savings(fired=fired, val_n=len(val_ids),
                             n_trials=max(1, args.n_trials),
                             decision=decision["decision"])

    payload = {
        "tag": tag, "screen_tag": screen_tag, "tier": args.tier,
        "current": cur_tag,
        "subset": sub,
        "reused_from_earlier_tiers": sorted(already & set(sub["ids"])),
        "fired_ids": new_ids,
        "paired": pair,
        "full_val_ceiling": ceiling,
        **decision,
        "savings": {**savings, "screen_cost_usd": screen_cost_usd},
        "promote_to": ("full-val evaluate + gate_check.py"
                       if decision["decision"] == "promote" else None),
        "note": ("A screen is TRIAGE. It may kill; it may never accept. Only "
                 "gate_check.py on FULL val (Δ̄ > k·SE and no regression) accepts."),
    }
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / f"{screen_tag}.json").write_text(json.dumps(payload, indent=2),
                                                encoding="utf-8")
    run_dir.log_event("screen", tag=tag, tier=args.tier, ids=sub["ids"],
                      fired=fired, decision=decision["decision"],
                      mean_delta=decision["mean_delta"], se=decision["se"],
                      n=decision["n"], inconclusive=decision["inconclusive"],
                      net_rollouts=savings["net_rollouts"], rationale=sub["rationale"])
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
