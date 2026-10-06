"""plan_round — propose a round's branch plan from diagnose's clusters (issue #665,
workstream 2).

Forensic finding this exists for (``run_20261003_184253``): every round forked exactly
one candidate, serially, with no stated reason N was 1 rather than more — ``round.py``
has supported N siblings since #437 and nothing ever decided N. This script is the
missing decision step the agent-optimize loop CALLS before creating any candidate dir:
read diagnose's clusters + the run's current :class:`~cap_evolve.candidate_graph.CandidateGraph`
state + remaining budget, and PROPOSE a branch plan — one slot per coherent root-cause
group, each with a textual hypothesis stub and an estimated branch count the calling
agent can accept, shrink, or override.

It is deterministic clustering/grouping arithmetic, NOT a judgement call: no LLM call
lives here, and the one judgement this script is explicitly not allowed to make is "the
answer is 3" — see ``estimate_branches``'s docstring. The calling agent reasons over the
emitted JSON (writes the actual hypothesis text, decides whether to trust the estimate)
and creates candidate dirs itself; this script never creates one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

import spend  # sibling script — reuses its own affordability check, see spend.py's docstring

from cap_evolve import RunDir
from cap_evolve.candidate_graph import CandidateGraph
from cap_evolve.specfile import spec_for_run

#: Two cluster signatures merge into one slot when their token overlap meets this —
#: literally diagnose/cluster.py's own OVERLAP_MIN threshold and formula
#: (|A∩B| / min(|A|,|B|)), reproduced here (not imported) to avoid a cross-skill-directory
#: import for one three-line formula; keep the two in sync if either threshold moves.
OVERLAP_MIN = 0.5

#: Safety CEILING on branches per slot, not a target — a slot's estimate climbs with its
#: own cluster count/uncertainty (see ``estimate_branches``) and is only ever clamped
#: down by this when it would, independent of the diagnosis, overload the round.
DEFAULT_MAX_BRANCHES_PER_SLOT = 3

#: A group's share of this round's TOTAL score_lost at or above which its single-cluster
#: slot gets a second branch — "this is the one cluster carrying most of the damage this
#: round, worth trying two implementation approaches on" rather than "there happen to be N
#: clusters bundled here" (the ``len(group)`` term already covers that case).
HIGH_STAKES_SHARE = 0.4


def _tokens(signature: str | None) -> frozenset[str]:
    return frozenset((signature or "").split())


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def group_clusters(clusters: list[dict], overlap_min: float = OVERLAP_MIN) -> list[list[dict]]:
    """Group clusters whose signatures overlap >= ``overlap_min`` into one slot each.

    Union-find over the pairwise overlap relation (transitive), the same shape
    diagnose/cluster.py uses to merge failures into clusters in the first place — one
    level up, merging clusters that likely share an implementation surface (same tool/
    field named in both signatures) into one candidate slot instead of one each.
    Deterministic and order-preserving: group order follows the first cluster that
    opened each group.
    """
    n = len(clusters)
    keys = [_tokens(c.get("signature")) for c in clusters]
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _overlap(keys[i], keys[j]) >= overlap_min:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)

    groups: dict[int, list[dict]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(clusters[i])
    return [groups[k] for k in sorted(groups)]


def estimate_branches(group: list[dict], all_groups: list[list[dict]],
                       max_cap: int = DEFAULT_MAX_BRANCHES_PER_SLOT) -> int:
    """How many sibling candidates this ONE slot's hypothesis is worth trying.

    A function of this slot's own evidence, never a constant:

      * ``len(group)`` — distinct clusters bundled into this slot (they overlapped
        enough to share one implementation surface, but each is still a separate root
        cause the single edit has to actually resolve; more of them bundled is more
        uncertainty about whether one edit covers all of them, worth hedging with
        another branch).
      * a stakes bump of +1 when this slot is the SOLE slot carrying >= ``HIGH_STAKES_SHARE``
        of the WHOLE round's score_lost, by a clear margin over the runner-up — "the one
        cluster carrying most of the damage this round, worth trying two implementation
        approaches on", not every slot that happens to clear the threshold independently.

    ``max_cap`` only ever clamps the result DOWN; it is read from ``--max-branches-per-
    slot`` (a safety ceiling, see the module docstring) and is never added to or used as
    the estimate itself — the function must be able to return 1 for a single small
    cluster and more than ``max_cap`` worth of raw signal for a large bundled/high-stakes
    one before being clamped, or the ceiling and the estimate would be the same number
    by construction, which is exactly the "always N" bug this exists to avoid.
    """
    total_lost = sum(float(c.get("score_lost") or 0.0) for grp in all_groups for c in grp)
    shares = [
        (sum(float(c.get("score_lost") or 0.0) for c in grp) / total_lost) if total_lost > 0 else 0.0
        for grp in all_groups
    ]
    this_lost = sum(float(c.get("score_lost") or 0.0) for c in group)
    share = (this_lost / total_lost) if total_lost > 0 else 0.0
    # The share bump only means something when OTHER slots exist to compare against —
    # with a single slot in the whole round its "share" of the total is trivially 1.0,
    # which would make every lone cluster look high-stakes regardless of score_lost.
    # It must also go to AT MOST ONE slot per round: two unrelated clusters that each
    # independently clear HIGH_STAKES_SHARE (e.g. two slots splitting the damage ~50/50)
    # are not "the one cluster carrying most of the damage" — require this slot's share
    # to be the round's unique maximum, by a clear margin over the runner-up.
    top = max(shares) if shares else 0.0
    runner_up = sorted(shares, reverse=True)[1] if len(shares) > 1 else 0.0
    is_sole_leader = share == top and shares.count(top) == 1
    high_stakes = (
        len(all_groups) > 1
        and is_sole_leader
        and top >= HIGH_STAKES_SHARE
        and (runner_up <= 0 or top >= 1.5 * runner_up)
    )
    raw = len(group) + (1 if high_stakes else 0)
    return max(1, min(raw, max_cap))


def _hypothesis_stub(group: list[dict]) -> str:
    """A textual stub summarizing the group's clusters — for the calling agent to WRITE
    the real hypothesis against, not a hypothesis itself. No LLM call here (see module
    docstring); this is string formatting over already-deterministic cluster output.
    """
    sigs = [c.get("signature") or c.get("tag") or "(unlabeled)" for c in group]
    tasks = sorted({str(t) for c in group for t in (c.get("tasks") or [])})
    return (f"root cause(s): {', '.join(sigs)}; affects task(s) {', '.join(tasks)} "
            f"-- fill in the actual mechanism and fix before creating this candidate")


def plan_round(clusters: list[dict], candidate_graph: CandidateGraph | None,
               afford: dict | None, overlap_min: float = OVERLAP_MIN,
               max_branches_per_slot: int = DEFAULT_MAX_BRANCHES_PER_SLOT) -> dict:
    groups = group_clusters(clusters, overlap_min)
    slots = []
    for i, group in enumerate(groups, start=1):
        branches = estimate_branches(group, groups, max_branches_per_slot)
        slots.append({
            "slot_id": f"slot_{i}",
            "cluster_ids": [c.get("tag") or c.get("signature") for c in group],
            "cluster_count": len(group),
            "score_lost": round(sum(float(c.get("score_lost") or 0.0) for c in group), 4),
            "affected_tasks": sorted({str(t) for c in group for t in (c.get("tasks") or [])}),
            "hypothesis_stub": _hypothesis_stub(group),
            "estimated_branches": branches,
        })
    total_branches = sum(s["estimated_branches"] for s in slots)
    out = {
        "slots": slots,
        "total_slots": len(slots),
        "total_estimated_branches": total_branches,
        "max_branches_per_slot_cap": max_branches_per_slot,
        "overlap_min": overlap_min,
        "frontier": candidate_graph.frontier() if candidate_graph is not None else None,
    }
    if afford is not None:
        out["afford"] = afford
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="plan_round")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", default=None, help="for affordability's num_trials; optional")
    p.add_argument("--clusters", required=True,
                   help="path to a diagnose run.py JSON output (reads its 'clusters' key), "
                        "or a bare JSON list of cluster dicts")
    p.add_argument("--overlap-min", type=float, default=OVERLAP_MIN)
    p.add_argument("--max-branches-per-slot", type=int, default=DEFAULT_MAX_BRANCHES_PER_SLOT,
                   help="safety ceiling only -- NOT a target branch count (see module docstring)")
    p.add_argument("--n-trials", type=int, default=0,
                   help="trials per full-val eval for the affordability check; "
                        "default = the project spec's num_trials")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    payload = json.loads(Path(args.clusters).read_text(encoding="utf-8"))
    clusters = payload.get("clusters") if isinstance(payload, dict) else payload
    if not isinstance(clusters, list):
        print("--clusters must point to a diagnose output dict or a bare cluster list",
              file=sys.stderr)
        return 2

    cg = CandidateGraph.load(run_dir)

    afford = None
    project = Path(args.project) if args.project else None
    try:
        spec = spec_for_run(run_dir, project)
        n_trials = args.n_trials or int(spec.get("num_trials") or 1)
    except Exception:  # noqa: BLE001 — affordability is a courtesy, not required to plan
        spec, n_trials = {}, args.n_trials or 1

    groups_preview = group_clusters(clusters, args.overlap_min)
    n_siblings_preview = sum(
        estimate_branches(g, groups_preview, args.max_branches_per_slot)
        for g in groups_preview
    )
    if n_siblings_preview:
        try:
            afford = spend._afford(run_dir, spec, n_siblings_preview, n_trials)
        except Exception as e:  # noqa: BLE001 — same courtesy as above
            afford = {"error": str(e)[:300]}

    out = plan_round(clusters, cg, afford, args.overlap_min, args.max_branches_per_slot)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
