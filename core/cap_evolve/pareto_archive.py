"""ParetoArchive — the persistent bounded non-dominated frontier issue #684 item 1 is about.

``cap_evolve.gate.decide(mode="pareto")`` only ever compares ONE candidate against ONE
reference and keeps no state across calls — a one-shot pairwise dominance check, not a
frontier. That was issue #684's confirmed real-run bug: a spec declaring ``gate_mode: pareto``
had nowhere a frontier could actually live, so round.py excluded "pareto" from its own
``--mode`` choices rather than ever reaching it. This module is the missing persistent state:
round.py loads it once per round, tries to insert each gated candidate, and writes it back to
the run dir so it survives across rounds and process restarts.

Design: Cheng & Li (1997)'s bounded-archive scheme, as cited by Marler & Arora's MOO survey
(Struct Multidisc Optim 26:369-395, 2004) that issue #684 is grounded in —

  * **membership**: a candidate joins the archive iff no existing point *significantly*
    Pareto-dominates it, and it shows a *significant* win on at least one objective against
    at least one existing point (a point whose "lead" is pure measurement noise is neither a
    real dominator nor a real addition). "Significant" reuses
    ``cap_evolve.gate._objective_state`` — the SAME per-objective stderr-required floor
    issue #667 fixed (a missing/zero stderr on a non-reward objective is refused, never read
    as a free pass) — and ``cap_evolve.selection.dominates`` for the actual dominance
    arithmetic, rather than reimplementing either.
  * **maintenance**: inserting a new non-dominated point removes any existing point the new
    one now dominates (an archive member can be superseded, never only added over).
  * **bounded capacity**: once the archive exceeds ``capacity`` it evicts the point with the
    smallest NSGA-II crowding distance (Deb et al. 2002) — the point packed closest to its
    neighbors in objective space, keeping the archive spread across the whole frontier rather
    than clumped near one corner. Boundary (extreme) points on every objective always keep
    infinite distance, so the frontier's own extremes are never evicted first.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import selection
from .gate import ParetoObjectiveError, _objective_state
from .rundir import _atomic_write, _file_lock

ARCHIVE_VERSION = 1
#: ponytail: a flat default, not tuned per-benchmark; raise/lower via capevolve.yaml's
#: `pareto_archive_capacity` (round.py) once a real run shows it binds.
DEFAULT_CAPACITY = 15


@dataclass
class ArchivePoint:
    tag: str
    values: dict = field(default_factory=dict)   # {objective_name: raw value}
    stderr: dict = field(default_factory=dict)   # {objective_name: SE}, same keys as values
    round: int | None = None
    #: {task: [TrialRec.to_dict()]} (#711): per-trial records, so a PAIRWISE matched-success
    #: comparison against any member is possible from the archive alone. Empty for legacy points.
    per_task: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"tag": self.tag, "values": dict(self.values), "stderr": dict(self.stderr),
             "round": self.round}
        if self.per_task:  # absent for legacy points: their serialisation is unchanged
            d["per_task"] = {t: list(v) for t, v in self.per_task.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ArchivePoint":
        return cls(tag=d["tag"], values=dict(d.get("values") or {}),
                   stderr=dict(d.get("stderr") or {}), round=d.get("round"),
                   per_task=dict(d.get("per_task") or {}))

    @staticmethod
    def per_task_of(trials) -> dict:
        """Group ``objectives.TrialRec``s into the ``per_task`` payload."""
        out: dict = {}
        for t in trials:
            out.setdefault(t.task, []).append(t.to_dict())
        return out

    def matched_vs(self, other: "ArchivePoint", theta: float = 1.0) -> dict:
        """Matched-success cost of ``self`` relative to ``other`` (see ``objectives.matched_cost``)."""
        from . import objectives
        rec = lambda p: [objectives.TrialRec.from_dict(x) for v in p.per_task.values() for x in v]
        return objectives.matched_cost(rec(other), rec(self), theta)


def _states_vs(values: dict, stderr: dict, other_values: dict, other_stderr: dict,
              objectives: list[dict], k_se: float) -> dict[str, str]:
    """Per-objective "better"/"worse"/"tie" of ``values`` relative to ``other_values``.

    Exactly the comparison ``gate._verdict``'s own pareto branch makes between a candidate
    and its reference, lifted out so the archive can run it between any two points: a
    non-reward objective with no stderr on EITHER side raises ``ParetoObjectiveError`` (the
    #667 fix this module must not regress), and reward's SE is combined from both sides'
    stderr the same way ``gate._verdict`` combines ``candidate_stderr``/``current_stderr``.
    """
    states = {}
    for obj in objectives:
        name, direction = obj["name"], obj.get("direction", "maximize")
        if name not in other_values:
            # ``try_insert`` already validated the NEW candidate's ``values`` has every
            # declared objective; an existing archive point can still be missing one (e.g.
            # seeded before an objective was declared, or from a harness that silently
            # omitted it) — refuse the same way gate.py's own missing-metric case does,
            # rather than a raw KeyError below.
            raise ParetoObjectiveError(
                f"pareto archive: existing archive point is missing declared objective "
                f"{name!r} (have: {sorted(other_values)!r}) — refusing to compare against "
                "an incomplete archive point")
        raw_delta = values[name] - other_values[name]
        signed = raw_delta if direction == "maximize" else -raw_delta
        sa, sb = stderr.get(name), other_stderr.get(name)
        if name != "reward" and (sa is None or sb is None):
            raise ParetoObjectiveError(
                f"pareto archive: objective {name!r} has no stderr on one side — refusing "
                "to fall back to a float-noise epsilon bar for a non-reward objective")
        se = ((sa or 0.0) ** 2 + (sb or 0.0) ** 2) ** 0.5
        states[name] = _objective_state(signed, se, k_se)
    return states


class ParetoArchive:
    def __init__(self, objectives: list[dict], capacity: int = DEFAULT_CAPACITY,
                 points: list[ArchivePoint] | None = None):
        self.objectives = [{"name": o["name"], "direction": o.get("direction", "maximize")}
                            for o in objectives]
        self.capacity = max(1, int(capacity))
        self.points: list[ArchivePoint] = list(points or [])

    # ---- membership ---------------------------------------------------------

    def try_insert(self, tag: str, values: dict, stderr: dict, *, k_se: float = 1.0,
                   round_num: int | None = None, per_task: dict | None = None) -> tuple[bool, str]:
        """Attempt to add ``tag``. Returns ``(inserted, reason)``.

        ``values``/``stderr`` must carry every declared objective's name, ``"reward"``
        included (``stderr["reward"]`` may be 0.0 for a deterministic/n=1 measurement —
        only non-reward objectives are refused for a missing SE, same as ``gate.py``).
        """
        names = {o["name"] for o in self.objectives}
        missing = names - set(values)
        if missing:
            raise ParetoObjectiveError(
                f"pareto archive: objective(s) {sorted(missing)} missing from {tag!r}'s values")

        if not self.points:
            self.points.append(ArchivePoint(tag, dict(values), dict(stderr), round_num, dict(per_task or {})))
            return True, "first point in empty archive"

        any_win = False
        dominated_by_new = []
        for p in self.points:
            states = _states_vs(values, stderr, p.values, p.stderr, self.objectives, k_se)
            cand_score = {n: (1.0 if st == "better" else 0.0) for n, st in states.items()}
            p_score = {n: (1.0 if st == "worse" else 0.0) for n, st in states.items()}
            if selection.dominates(p_score, cand_score):
                return False, f"dominated by archive point {p.tag!r}"
            if any(st == "better" for st in states.values()):
                any_win = True
            if selection.dominates(cand_score, p_score):
                dominated_by_new.append(p.tag)
        if not any_win:
            return False, "no significant improvement over any existing archive point (tie)"

        self.points = [p for p in self.points if p.tag not in dominated_by_new]
        self.points.append(ArchivePoint(tag, dict(values), dict(stderr), round_num, dict(per_task or {})))
        evicted = self._evict()
        reason = "inserted (non-dominated, significant win on >=1 objective)"
        if dominated_by_new:
            reason += f"; superseded {dominated_by_new}"
        if evicted:
            reason += f"; evicted {evicted} by crowding distance (capacity {self.capacity})"
        return True, reason

    # ---- bounded capacity: NSGA-II crowding-distance eviction ---------------

    def _crowding_distances(self) -> dict[str, float]:
        pts = self.points
        n = len(pts)
        dist = {p.tag: 0.0 for p in pts}
        if n <= 2:
            return {p.tag: float("inf") for p in pts}
        for obj in self.objectives:
            name = obj["name"]
            ordered = sorted(pts, key=lambda p: p.values.get(name, 0.0))
            lo, hi = ordered[0].values.get(name, 0.0), ordered[-1].values.get(name, 0.0)
            dist[ordered[0].tag] = float("inf")
            dist[ordered[-1].tag] = float("inf")
            rng = hi - lo
            if rng <= 0:
                continue
            for i in range(1, n - 1):
                gap = ordered[i + 1].values.get(name, 0.0) - ordered[i - 1].values.get(name, 0.0)
                dist[ordered[i].tag] += gap / rng
        return dist

    def _evict(self) -> list[str]:
        evicted = []
        while len(self.points) > self.capacity:
            dist = self._crowding_distances()
            worst = min(self.points, key=lambda p: (dist.get(p.tag, 0.0), self.points.index(p)))
            self.points.remove(worst)
            evicted.append(worst.tag)
        return evicted

    # ---- persistence ----------------------------------------------------------

    def to_dict(self) -> dict:
        return {"version": ARCHIVE_VERSION, "objectives": list(self.objectives),
                "capacity": self.capacity, "points": [p.to_dict() for p in self.points]}

    @classmethod
    def from_dict(cls, d: dict) -> "ParetoArchive":
        if d.get("version") != ARCHIVE_VERSION:
            raise ValueError(
                f"pareto_archive: unknown archive schema version {d.get('version')!r} "
                f"(expected {ARCHIVE_VERSION})")
        return cls(objectives=d["objectives"], capacity=d.get("capacity", DEFAULT_CAPACITY),
                   points=[ArchivePoint.from_dict(p) for p in d.get("points") or []])

    def save(self, path: Path) -> None:
        """Write the archive, locked + atomic — same ``rundir.py`` pattern ``state.json``
        uses for its identical load->mutate->save read-modify-write cycle, so two
        processes touching the same run dir's archive don't tear or lose a write."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with _file_lock(path.with_name(f".{path.name}.lock")):
            _atomic_write(path, json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load_or_create(cls, path: Path, objectives: list[dict],
                       capacity: int = DEFAULT_CAPACITY) -> "ParetoArchive":
        """Read the persisted archive at ``path``, or start a fresh one.

        A version mismatch or corrupt file starts fresh rather than crashing the round —
        the archive is a cache of frontier state, not the run's source of truth (that is
        each candidate's own persisted rollouts, which this never touches).
        """
        if path.is_file():
            try:
                with _file_lock(path.with_name(f".{path.name}.lock")):
                    return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return cls(objectives=objectives, capacity=capacity)
