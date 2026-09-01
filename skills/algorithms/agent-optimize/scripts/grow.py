"""grow — buy more trials on a PROVISIONAL candidate, then re-gate at the pooled n.

A candidate is ``provisional`` (``commit.py --decision provisional``) when it is
directionally positive (Δ>0) but did not clear the significance gate at the n it was
measured at. That is sequential evidence, not a null result: the honest next step is
more trials on the SAME, UNMODIFIED candidate — never a new edit on top of unconfirmed
ground (see references/algorithm.md, "Provisional candidates").

This script:
  1. runs ``--add-trials`` NEW trials on the candidate's unchanged working copy, under a
     throwaway tag (so the new rollout files cannot collide with the candidate's own),
  2. pools the new trials with the candidate's existing val rollouts via
     ``loop.pool_split_results`` (concatenates per-task trial vectors, not two means),
  3. re-runs the SAME paired gate the candidate was first measured against, at the
     pooled n,
  4. merges the new rollout files onto the candidate's own tag on disk (renumbered past
     its existing trial indices) so a later ``gate_check.py --candidate <tag>`` or
     ``commit.py`` sees the full pooled history with no special-casing, and
  5. recommends ``promote`` / ``grow_again`` / ``abandon`` — capped at
     ``--max-growth-rounds`` (default 2): a provisional lineage that still has not
     resolved after 2 extra growth rounds must be abandoned, not grown again, so an
     unlucky early positive can only consume a bounded amount of extra budget.

Never edits the candidate directory — it is re-evaluated exactly as it is.
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
from cap_evolve.check import load_adapter
from cap_evolve.gate import decide
from cap_evolve.loop import pool_split_results

DEFAULT_MAX_GROWTH_ROUNDS = 2


def _existing_trial_count(run_dir: RunDir, tag: str, split: str) -> int:
    """How many trial files the candidate's OWN tag already has (any task; every task
    gets the same count, errored or not — see harness.evaluate_candidate)."""
    vdir = run_dir.rollouts / split
    if not vdir.exists():
        return 0
    # Track the HIGHEST trial index per task, then convert to a count once. Comparing a
    # running count against the next index instead (`max(count, idx) + 1`) over-counts
    # whenever glob order is not ascending, which leaves gaps in the merged indices.
    highest: dict = {}
    for f in vdir.glob(f"*__{tag}__t*.json"):
        tid = f.name.split(f"__{tag}__t")[0]
        idx = int(f.name.rsplit("__t", 1)[1].removesuffix(".json"))
        highest[tid] = max(highest.get(tid, -1), idx)
    return max(highest.values()) + 1 if highest else 0


def _merge_grow_trials(run_dir: RunDir, candidate: str, grow_tag: str, split: str,
                       offset: int) -> None:
    """Rename the throwaway tag's rollout files onto the candidate's own tag, at trial
    indices starting from ``offset`` — so the candidate's tag alone now carries the full
    pooled history and every downstream reader (gate_check.py, dashboard, LEDGER.md)
    needs no special-casing for a grown candidate."""
    vdir = run_dir.rollouts / split
    for f in sorted(vdir.glob(f"*__{grow_tag}__t*.json")):
        tid = f.name.split(f"__{grow_tag}__t")[0]
        idx = int(f.name.rsplit("__t", 1)[1].removesuffix(".json"))
        f.rename(vdir / f"{tid}__{candidate}__t{offset + idx}.json")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="grow")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--candidate", required=True,
                   help="the provisional candidate's tag == dir name")
    p.add_argument("--current", default=None,
                   help="tag to gate against; default = the run's current best_id")
    p.add_argument("--add-trials", type=int, required=True,
                   help="how many NEW trials to run on this candidate before re-gating")
    p.add_argument("--growth-round", type=int, required=True,
                   help="which growth attempt this is for this candidate (1, 2, ...)")
    p.add_argument("--max-growth-rounds", type=int, default=DEFAULT_MAX_GROWTH_ROUNDS)
    p.add_argument("--k-se", type=float, default=1.0)
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    adapter = load_adapter(Path(args.project))
    cur_tag = args.current or run_dir.best_id
    if not cur_tag:
        print(json.dumps({"error": "no --current tag and no best_id in the run dir"}, indent=2))
        return 2

    cand_dir = run_dir.candidate_dir(args.candidate)
    if not cand_dir.is_dir():
        print(json.dumps({"error": f"no snapshot for candidate {args.candidate!r} — "
                                   "commit.py --decision provisional first"}, indent=2))
        return 2

    existing = harness.split_result_from_rollouts(run_dir, args.candidate, "val")
    if not existing.per_task:
        print(json.dumps({"error": f"no existing val rollouts for {args.candidate!r} — "
                                   "this is not a candidate that was ever gated"}, indent=2))
        return 2

    # New trials go under a THROWAWAY tag first (never the candidate's own), so they
    # cannot collide with — or silently overwrite — the trials already on disk.
    grow_tag = f"{args.candidate}__grow{args.growth_round}"
    try:
        base_seed = int(run_dir.read_splits().seed)
    except Exception:  # noqa: BLE001
        base_seed = 0
    # Offset the new batch's seeds well clear of any prior growth round's, so re-running
    # a real (non-deterministic) target draws genuinely new trials rather than replaying
    # ones already on disk. ponytail: a fixed 1000-per-round stride, not exact bookkeeping
    # of how many seeds a prior round actually consumed — plenty of headroom at the trial
    # counts this gate is meant for.
    new_result = harness.evaluate_candidate(
        adapter, cand_dir, run_dir=run_dir, split="val", n_trials=args.add_trials,
        tag=grow_tag, base_seed=base_seed + 1000 * args.growth_round)

    pooled = pool_split_results(existing, new_result)

    cur = harness.split_result_from_rollouts(run_dir, cur_tag, "val")
    deltas = harness._paired_deltas(cur, pooled)
    d = decide(cur.reward, pooled.reward, split="val", mode="paired", k_se=args.k_se,
               candidate_stderr=pooled.stderr, current_stderr=cur.stderr,
               paired_deltas=deltas, coverage=pooled.coverage, run_dir=run_dir)
    verdict = "indecisive" if d.indecisive else ("accept" if d.accept else "reject")

    # Merge the new trials onto the candidate's OWN tag now that the pooled numbers are
    # computed, so a re-run of gate_check.py --candidate <candidate> (or another grow.py
    # call for round N+1) sees the same pooled n with no special-casing.
    offset = _existing_trial_count(run_dir, args.candidate, "val")
    _merge_grow_trials(run_dir, args.candidate, grow_tag, "val", offset)

    if verdict == "accept":
        recommendation = "promote"
    elif verdict != "indecisive" and d.delta > 0 and args.growth_round < args.max_growth_rounds:
        recommendation = "grow_again"
    else:
        recommendation = "abandon"

    run_dir.log_event("provisional_grow", candidate=args.candidate, growth_round=args.growth_round,
                      add_trials=args.add_trials, pooled_n=len(deltas or []),
                      pooled_val=pooled.reward, verdict=verdict, recommendation=recommendation)

    # Persist the POOLED gate row in the same `work/<table>.json` shape `round.py` writes,
    # because `commit.py` reads such a table to recover the verdict (`_gate_row`, newest mtime)
    # and the structured gate numbers it attaches to the decision event
    # (`_round_gate_numbers`, which prefers a `grow_<cand>_r<k>.json` over the round's own row
    # for exactly this candidate). Without this the final commit on a grown candidate books the
    # round's PRE-growth numbers — and a `promote` would be logged as `gate_verdict: reject`,
    # reading as a driver override of a gate that in fact accepted at the pooled n.
    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / f"grow_{args.candidate}_r{args.growth_round}.json").write_text(
        json.dumps({"grown": args.candidate, "growth_round": args.growth_round,
                    "candidates": [{
                        "tag": args.candidate,
                        "reward": pooled.reward,
                        "gate_delta": d.delta,
                        "gate_threshold": d.threshold,
                        "stderr": pooled.stderr,
                        "n": len(deltas or []),
                        "k_se": args.k_se,
                        "resolvable_effect_size": d.resolvable_effect_size,
                        "verdict": verdict,
                    }]}, indent=2), encoding="utf-8")

    print(json.dumps({
        "candidate": args.candidate,
        "growth_round": args.growth_round,
        "max_growth_rounds": args.max_growth_rounds,
        "current": {"tag": cur_tag, "reward": cur.reward, "stderr": cur.stderr},
        "pooled": {"reward": pooled.reward, "stderr": pooled.stderr, "n_tasks": pooled.n_tasks},
        "gate": d.to_dict(),
        "paired_n": len(deltas or []),
        "verdict": verdict,
        "recommendation": recommendation,
        "next": ("scripts/commit.py --decision accept" if recommendation == "promote" else
                 f"scripts/grow.py --growth-round {args.growth_round + 1}" if recommendation == "grow_again" else
                 "scripts/commit.py --decision reject --reject-basis gate"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
