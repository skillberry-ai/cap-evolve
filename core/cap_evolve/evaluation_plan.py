"""evaluation_plan — what to measure for ONE candidate, and why (issue #665, workstream 2).

Forensic finding this exists for (``run_20261003_184253``): 7 of 8 candidates paid a
full 90-rollout val gate although each targeted <=7 tasks, and 6 of 8 screens came back
``inconclusive`` because their chosen subset was too narrow to resolve anything — i.e.
subset selection and the skip-full-val decision were both ad hoc. ``screen.py`` already
runs a tiered subset eval and ``round.py`` already decides promote/kill on it; this
module is the missing piece in FRONT of that: a small, structured, PERSISTED record of
which tasks a candidate's hypothesis should move (``affected_tasks``), a few currently-
passing tasks to watch for breakage (``regression_sentinels``), which evaluation stage
that calls for, and the one-paragraph reasoning — so screen.py's subset and round.py's
"did we even need full val" decision have a documented input instead of being
re-reasoned from scratch (and re-worded into boilerplate, #585) every round.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: Stage vocabulary (lowest-cost first). A candidate normally starts at 1 and only
#: climbs when its own targeted evidence says to — nothing here *runs* an eval, this
#: is a plan a caller (screen.py / round.py / the agent-optimize loop) acts on.
STAGE_STATIC = 0          # static/unit: no rollout at all (lint/micro-test only)
STAGE_TARGETED_SMALL = 1  # a few affected tasks, 1 trial
STAGE_EXPANDED_CLUSTER = 2  # the whole targeted cluster(s), still a subset of val
STAGE_REGRESSION = 3      # affected tasks + regression sentinels, still a subset
STAGE_BROAD_PARTIAL = 4   # most but not all of val
STAGE_FULL = 5            # full val x num_trials — the only accept-capable gate

#: How many currently-passing tasks to sample as regression sentinels. Small and fixed
#: because this is a WATCH-list, not a second measurement surface: screen.py's own paired
#: comparison against the parent already covers broader regression risk; this is extra,
#: cheap, targeted insurance on top.
_N_SENTINELS = 3


@dataclass
class EvaluationPlan:
    affected_tasks: list[str] = field(default_factory=list)
    regression_sentinels: list[str] = field(default_factory=list)
    stage: int = STAGE_TARGETED_SMALL
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "affected_tasks": list(self.affected_tasks),
            "regression_sentinels": list(self.regression_sentinels),
            "stage": self.stage,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvaluationPlan":
        return cls(
            affected_tasks=list(d.get("affected_tasks") or []),
            regression_sentinels=list(d.get("regression_sentinels") or []),
            stage=int(d.get("stage", STAGE_TARGETED_SMALL)),
            rationale=str(d.get("rationale") or ""),
        )


#: Above this many affected tasks a single cluster's edit is no longer "targeted" — the
#: forensic run's own targeted edits topped out at 7 tasks; this gives real headroom above
#: that before escalating stage, not a number tuned to that run alone.
_TARGETED_MAX = 10


def build_evaluation_plan(cluster: dict, graph=None, history: dict | None = None) -> EvaluationPlan:
    """Compute a candidate's :class:`EvaluationPlan` from the diagnose cluster(s) it targets.

    ``cluster`` is one diagnose ``cluster.py`` record, OR a dict with the same shape
    produced by grouping several of them (``plan_round.py``'s slots) — anything with
    ``tasks: [...]`` and optionally ``score_lost``/``signature``. ``graph`` (a
    :class:`~cap_evolve.candidate_graph.CandidateGraph`, optional) is accepted for a
    future tie-in (e.g. "this cluster already failed at stage 2 on an ancestor, start
    there") but unused today — no history to read it from yet. ``history`` is diagnose's
    own run output dict (``{"kept_good": [...], "clusters": [...], ...}``) when available;
    without it there is simply nothing to sample sentinels from and the list is empty
    rather than guessed.

    affected_tasks: the cluster's own failing tasks — exactly what the hypothesis claims
    it will move, nothing broader.

    regression_sentinels: up to ``_N_SENTINELS`` tasks already at 100% (``history["kept_good"]``)
    NOT in ``affected_tasks``, sampled evenly across the list for stable coverage rather than
    always the same prefix.
    # ponytail: "same tool/policy surface" (the ideal match) needs per-task tool-call data
    # diagnose() does not keep for PASSING tasks (only failures carry a trace pointer) — a
    # plain evenly-spaced sample of kept_good is the honest proxy available today. Upgrade
    # when diagnose's reflective_dataset is extended to passing tasks too.

    stage: STAGE_TARGETED_SMALL while the affected set stays small (<= _TARGETED_MAX,
    the forensic run's own targeted edits topped out at 7); STAGE_EXPANDED_CLUSTER once a
    candidate's hypothesis itself claims a broader surface than that.
    """
    affected = sorted({str(t) for t in (cluster.get("tasks") or [])})
    kept_good = [str(t) for t in ((history or {}).get("kept_good") or []) if str(t) not in affected]
    sentinels: list[str] = []
    if kept_good:
        n = min(_N_SENTINELS, len(kept_good))
        step = max(1, len(kept_good) // n)
        sentinels = sorted(kept_good[i] for i in range(0, len(kept_good), step)[:n])

    stage = STAGE_TARGETED_SMALL if len(affected) <= _TARGETED_MAX else STAGE_EXPANDED_CLUSTER
    stage_name = "targeted-small" if stage == STAGE_TARGETED_SMALL else "expanded-cluster"
    rationale = (
        f"{len(affected)} affected task(s) from cluster "
        f"{cluster.get('signature') or cluster.get('tag') or '(unlabeled)'!r} "
        f"(score_lost={cluster.get('score_lost')}) -> stage {stage} ({stage_name}); "
        f"{len(sentinels)} regression sentinel(s) sampled from "
        f"{len(kept_good)} currently-passing task(s) not in the affected set."
    )
    return EvaluationPlan(affected_tasks=affected, regression_sentinels=sentinels,
                          stage=stage, rationale=rationale)


def persist_evaluation_plan(run_dir, candidate_id: str, plan: EvaluationPlan) -> Path:
    """Write ``plan`` to ``<candidate_dir>/evaluation_plan.json`` — the same convention
    ``commit.py``/``_diagnosis_targets`` already use for ``DIAGNOSIS.json`` (one JSON
    file per candidate, inside its own snapshot dir). Overwrites any prior plan for this
    candidate; callers that want history should look at ``graph.jsonl``'s append log
    instead, same as every other per-candidate artifact.
    """
    cdir = Path(run_dir.candidate_dir(candidate_id))
    cdir.mkdir(parents=True, exist_ok=True)
    out = cdir / "evaluation_plan.json"
    out.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return out
