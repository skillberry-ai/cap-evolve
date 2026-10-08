"""task_ownership — per-task best-scorer tracking for parent-selection diversity
(issue #684 item 3, GEPA-inspired).

GEPA's Algorithm 2 tracks, PER TRAINING INSTANCE i, which candidate(s) currently
score best on it: ``S*[i] = max over candidates of score(candidate, i)``,
``P*[i]`` the set of candidates achieving that max. The next parent to mutate is
then sampled weighted by ``f[candidate] = count of i where candidate in P*[i]`` —
GEPA's single biggest ablated lever (paper: +12.44% vs +6.05% greedy, +5.11% beam).

This is a DIFFERENT structure from the reward+cost 2D Pareto archive (#684 item
1/2, a separate module): that one is multi-objective over few candidates and
decides accept/reject. This one is single-objective (one score per task) over
many tasks, and decides nothing — it only SURFACES which non-champion candidates
own tasks the champion doesn't, as a signal ``plan_round.py`` exposes to the
driving agent. No accept/reject/branch decision is made here.

Scores come from each candidate's already-persisted val rollouts
(``harness.split_result_from_rollouts(...).per_task``) — this module adds no new
measurement and never re-runs anything.
"""

from __future__ import annotations


def compute_ownership(per_task_by_candidate: dict[str, dict[str, float]]) -> dict:
    """Given ``{candidate_id: {task_id: score}}``, compute per-task best-scorer(s).

    Returns::

        {
          "owners": {task_id: [candidate_id, ...]},   # tied at that task's max, sorted
          "best_score": {task_id: float},
          "ownership_count": {candidate_id: int},      # GEPA's f[candidate]: how many
                                                         # tasks this candidate owns
                                                         # (solely or tied)
        }

    A candidate missing a task (never evaluated on it) simply doesn't compete for
    it. Ties are exact float equality — these scores already share one measurement
    pipeline (``split_result_from_rollouts``), so no epsilon is needed here.
    """
    task_ids = sorted({t for pt in per_task_by_candidate.values() for t in pt})
    owners: dict[str, list[str]] = {}
    best_score: dict[str, float] = {}
    for t in task_ids:
        scores = {cid: pt[t] for cid, pt in per_task_by_candidate.items() if t in pt}
        if not scores:
            continue
        m = max(scores.values())
        best_score[t] = m
        owners[t] = sorted(cid for cid, s in scores.items() if s == m)

    ownership_count = {cid: 0 for cid in per_task_by_candidate}
    for cids in owners.values():
        for cid in cids:
            ownership_count[cid] += 1
    return {"owners": owners, "best_score": best_score, "ownership_count": ownership_count}


#: Statuses whose candidate carries no reusable val evidence for ownership purposes:
#: "proposed" (not yet screened/measured) and "superseded" (bytes absorbed into/lost
#: to another node — not a distinct lineage worth surfacing). Everything else
#: ("screened", "gated", "accepted", "rejected") has real per-task val scores on
#: disk, INCLUDING "rejected" — a candidate can lose the aggregate gate yet still
#: cleanly win specific tasks the champion doesn't, which is exactly the signal
#: this module exists to surface (issue #684 item 3).
_NO_EVIDENCE_STATUSES = frozenset({"proposed", "superseded"})


def eligible_candidate_ids(candidate_graph) -> list[str]:
    """Candidate ids worth pulling val per-task scores for: every node whose status
    implies a full-val measurement actually ran, per ``_NO_EVIDENCE_STATUSES`` above.
    Sorted for determinism."""
    return sorted(
        nid for nid, n in candidate_graph._nodes.items()  # noqa: SLF001 — same module family
        if n.get("status") not in _NO_EVIDENCE_STATUSES
    )


def from_run(run_dir, candidate_graph, split: str = "val") -> dict:
    """Build ownership from a real run: pull val per-task rewards for every
    :func:`eligible_candidate_ids` candidate via ``harness.split_result_from_rollouts``
    (the canonical read every other gate/screen/merge script already uses) and feed
    :func:`compute_ownership`. Candidates with no persisted val rollouts (score read
    comes back empty) simply contribute nothing."""
    from cap_evolve import harness  # local import: avoids a hard harness<->this-module cycle

    per_task_by_candidate: dict[str, dict[str, float]] = {}
    for cid in eligible_candidate_ids(candidate_graph):
        try:
            sr = harness.split_result_from_rollouts(run_dir, cid, split)
        except Exception:  # noqa: BLE001 — a missing/unreadable tag contributes nothing
            continue
        rows = sr.per_task or []
        if rows:
            per_task_by_candidate[cid] = {pt["task_id"]: float(pt.get("reward", 0.0))
                                           for pt in rows}
    return compute_ownership(per_task_by_candidate)
