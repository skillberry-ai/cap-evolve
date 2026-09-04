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
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter
from cap_evolve.subsample import (
    full_val_ceiling, paired_deltas_on, screen_decision, screen_savings,
    select_screen_subset,
)

#: Rung → fraction of val screened. Tier 3 is "almost full val" for the rare case
#: where full val is very large; the real gate is still a separate full-val eval.
TIER_FRAC = {1: 0.25, 2: 0.5, 3: 0.75}

#: Absolute floor on subset width, independent of the fraction. Was 3, and 3 is
#: MEASURED to be too narrow: on a 12-task val, tier 1 = round(0.25·12) = 3, and the
#: run in docs/RESULTS.md produced a screen that reported ``fixed: ["44"]`` on a 3-task
#: subset when full val showed task 44 was never fixed — a false positive on a third of
#: the evidence. 6 is the smallest width where the paired SE over {-1,0,+1} deltas is
#: not dominated by a single task. It only binds on small val splits; a 100-task val
#: still screens at the 25% fraction.
MIN_K = 6


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
                   help="kill only when Δ̄ + k·SE < 0 on the subset (default 1.0)")
    p.add_argument("--broken", default="",
                   help="comma-separated task ids a previous edit broke — screened first")
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

    frac = TIER_FRAC[args.tier]
    k = args.k or max(MIN_K, int(round(frac * len(val_ids))))
    seed = args.seed if args.seed is not None else int(run_dir.read_splits().seed) + args.tier
    broken = [b for b in (args.broken or "").split(",") if b.strip()]
    sub = select_screen_subset(parent.per_task, k=k, seed=seed,
                               holdout_frac=args.holdout_frac,
                               broken_ids=[b.strip() for b in broken])

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
                               regressed=pair["regressed"])

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
