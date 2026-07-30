"""Plateau / convergence detection with escalating interventions.

The engine already stops on *budget* (iterations, metric calls, USD) and on the
``stall`` counter (N consecutive non-accepts). Neither answers the question this
module answers: **is the search still making progress, or is it grinding a dead
region?** ``stall`` counts rejections, and a rejection is not the same thing as a
lack of progress.

The criterion — why counting rejections is the wrong thing
---------------------------------------------------------
Optimization is legitimately spiky: several rejected iterations followed by a
breakthrough is the normal shape of a run, so "N rejects in a row → stop" kills
productive searches. The fix is to look at *what the gate actually rejected*.

``gate.decide`` accepts iff ``Δ̄ > k_eff·SE(Δ)``. That splits rejections into two
qualitatively different classes:

* **near-miss** — ``Δ > 0`` but below the significance bar. The edit *did* move the
  score; the run has not proven it yet. This is progress-in-flight, and #113's
  Student-t small-sample correction makes it *strictly more common* (at n=5 the bar
  is 1.14× wider than the old z bar, at n=2 it is 1.84× wider), so on small val
  splits a healthy run now produces many near-misses. A heuristic that counted
  those as "no progress" would over-trigger exactly where #113 tightened the bar.
* **dead** — ``Δ ≤ 0``. The edit did not move the score at all, in the direction it
  was supposed to.

So ``run_length`` = the count of **trailing iterations that produced no new global
best and were not a near-miss**. Concretely, an iteration is *dead* when it neither
raised best-val nor moved the score in the right direction:

* accepted **and** a new global best → alive, streak resets (real progress).
* rejected with **Δ > 0** (near-miss) → alive, streak resets.
* rejected with **Δ ≤ 0** → dead.
* accepted but **not** a new best → dead *for the streak* (best-val velocity is 0,
  which is what the user is paying for) — but see the ratchet below.

That last case is why velocity is not a separate condition: it is folded in. It also
matters in practice — GEPA can accept a frontier specialist that beats its own parent
without ever topping the incumbent best, and a naive accept-reset lets such a run
grind forever at flat best-val.

**The ratchet:** an accept in the streak, even a non-best one, caps escalation at
``warn``. Only a streak with *zero* accepts can reach ``diversify`` or ``stop``. A run
that is still clearing the honest val gate every iteration is doing the thing it was
built to do — widening a per-instance Pareto frontier is *GEPA's mechanism*
(arXiv:2507.19457), not a failure — so it gets a warning and no behavioural
intervention: telling such an optimizer "the direction is dead, change approach" would
be factually wrong. A run that has stopped accepting entirely does get stopped.
Stopping early is the expensive error, so the conservative side is the default.

**The honest cost of the Δ≤0 rule.** A run that produces N consecutive *regressions* and
would have broken through on N+1 is stopped at N. No ratchet saves it (zero accepts, and
a regression is not a near-miss). This is inherent to any rule keyed on the sign of Δ,
it is the real price of having a ``stop`` at all, and it is why the window defaults to 6
and ``plateau_stop: false`` exists. A genuine Pareto trade on a tiny val split (fixes one
task, breaks another, net Δ=0) reads as dead for the same reason.

**Resume carries the streak.** ``assess`` reads the whole event log, so ``--resume`` on a
plateaued run re-derives ``stop`` before spending an iteration. That is deliberate — a
dead region is still dead after a restart, and re-spending budget to rediscover it is the
error this module exists to prevent. ``plateau_stop: false`` / ``--no-plateau-stop`` is
the escape hatch.

Escalation ladder (``run_length`` vs the configured window W and step E)::

    run_length >= W            -> "warn"       plateau_warning event only
    run_length >= W + E        -> "diversify"  + a paradigm-shift prompt block,
                                               + exhausted lineages de-prioritized
    run_length >= W + 2*E      -> "stop"       loop breaks (if plateau_stop)

Defaults W=6, E=2 → warn at 6, diversify at 8, stop at 10 dead iterations. Any accept in
the streak caps this at ``warn`` (the ratchet, above).

Per-lineage exhaustion is a *different* question, is reported separately, and uses a
*narrower* deadness test (:func:`_lineage_dead`): an ACCEPT is never dead ground for a
lineage, whatever it means for global best-val velocity. A single parent can be exhausted
(its last K children all rejected with Δ≤0) while the global search is fine, because
another lineage is accepting. GEPA uses this to steer its Pareto sampling away from the
dead region without stopping the run; hill-climb/skillopt are single-lineage (parent is
always the current best), so for them exhaustion coincides with the global signal and
only reaches the prompt.

Note the asymmetry is deliberate: the global level *does* count an accept that did not
top the best as dead-for-the-streak, because the zero-accept ratchet means such a streak
can never be killed. Per lineage there is no ratchet — an exhausted lineage is silently
dropped from GEPA's sampling pool — so the same clause there would steer the search off
its most productive lineage with nothing to catch it.

Not to be confused with #118's run *liveness* states (``live``/``stalled``/
``crashed``/``done``), which are derived from events.jsonl mtime: *stalled* means
nothing is happening at all. *Plateaued* means plenty is happening and none of it
helps. Different question, different vocabulary, different event kind.

Pure stdlib.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import rundir as _rundir

# Fallback for the shared iteration-event kind list (rundir.ITERATION_EVENT_KINDS,
# added by #109/PR199). ponytail: one definition, preferred at runtime; delete this
# literal once #199 lands. Never hand-filter on kind == "step" — GEPA emits
# gepa_val_gate and would silently vanish.
#
# ``skillopt_step`` is deliberately ABSENT. SkillOpt delegates to ``harness.run_step``,
# which already logs ``step`` for the SAME candidate — and carries ``parent``/``parent_val``,
# which ``skillopt_step`` does not. Listing both counted every SkillOpt iteration TWICE,
# firing the ladder at half the configured window (stop at iteration 5 of a window=6
# ladder) and recording a genuine near-miss once alive and once dead. PR #219 owns the
# root fix (dropping the kind from ``rundir.ITERATION_EVENT_KINDS``); this pre-#199
# fallback only has to agree with it. ``skillopt_step`` stays in events.jsonl as an audit
# record — it is just not an *iteration* event. Do NOT dedupe by candidate id instead:
# SkillOpt re-mints ``so_eNNsMM`` after ``--resume``, so id-keyed dedup drops real
# resumed iterations (verified on #219).
_FALLBACK_KINDS = ("step", "gepa_val_gate")

# GEPA's cheap local minibatch gate. A child killed here never reaches the val gate,
# so it emits no iteration event — but it IS a spent iteration that produced no
# movement (sum(child) <= sum(parent) is the pass condition), and a GEPA run can grind
# for many iterations without ever logging gepa_val_gate. Counted as dead.
_LOCAL_GATE_KIND = "gepa_local_gate"


@dataclass
class PlateauConfig:
    """Thresholds. All config-driven from ``capevolve.yaml`` / algorithm CLI flags."""

    window: int = 6              # dead iterations before the first warning
    escalate_every: int = 2      # further dead iterations per escalation step
    lineage_window: int = 4      # dead children of one parent before it is exhausted
    stop: bool = True            # allow the ladder to reach "stop"; False = warn/diversify only

    @classmethod
    def from_spec(cls, spec: dict | None) -> "PlateauConfig":
        """``plateau_stop: false`` is the off switch; a 0/negative window is NOT.

        ``plateau_window: 0`` used to silently revert to the default (``or d.window``),
        which reads like "off" and behaves like "on at 6". It now means the same thing as
        ``plateau_stop: false`` — the honest reading of "disable this" — rather than
        quietly ignoring the user.
        """
        s = spec or {}
        d = cls()
        if s.get("plateau_window") is not None and int(s["plateau_window"] or 0) <= 0:
            return cls(stop=False, window=10 ** 9)   # unreachable ladder == disabled
        return cls(
            window=max(2, int(s.get("plateau_window") or d.window)),
            escalate_every=max(1, int(s.get("plateau_escalate_every") or d.escalate_every)),
            lineage_window=max(2, int(s.get("plateau_lineage_window") or d.lineage_window)),
            stop=(d.stop if s.get("plateau_stop") is None else bool(s.get("plateau_stop"))),
        )

    @property
    def warn_at(self) -> int:
        return self.window

    @property
    def diversify_at(self) -> int:
        return self.window + self.escalate_every

    @property
    def stop_at(self) -> int:
        return self.window + 2 * self.escalate_every


LEVELS = ("ok", "warn", "diversify", "stop")


@dataclass
class PlateauState:
    level: str = "ok"
    run_length: int = 0           # trailing iterations rejected with Δ <= 0
    iterations: int = 0           # iterations observed in total
    best_val: float = 0.0
    velocity: float = 0.0         # best-val gain over the trailing streak (0 while plateaued)
    near_misses: int = 0          # rejected-but-Δ>0 seen in the last `window` iterations
    accepts: int = 0
    accepts_in_streak: int = 0   # accepts inside the dead streak -> caps escalation at diversify
    exhausted_lineages: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def should_stop(self) -> bool:
        return self.level == "stop"

    @property
    def should_diversify(self) -> bool:
        return self.level in ("diversify", "stop")

    def to_dict(self) -> dict:
        return asdict(self)


def _iteration_events(run_dir) -> list[dict]:
    """Gated iterations (accept/reject with a val number), via the shared reader."""
    fn = getattr(run_dir, "iteration_events", None)
    if callable(fn):
        return fn()
    kinds = getattr(_rundir, "ITERATION_EVENT_KINDS", _FALLBACK_KINDS)
    cand = getattr(_rundir, "iteration_candidate", lambda e: e.get("candidate") or e.get("candidate_id"))
    out = []
    for rec in _raw_events(run_dir):
        if rec.get("kind") in kinds and cand(rec):
            out.append(rec)
    return out


def _raw_events(run_dir) -> list[dict]:
    out: list[dict] = []
    try:
        path = run_dir.events_path
        if not path.exists():
            return out
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except Exception:  # noqa: BLE001 — a torn/absent log must not break the loop
        return out
    return out


def series(run_dir) -> list[dict]:
    """Every spent iteration in order, as ``{candidate, parent, accepted, delta}``.

    Merges the gated iterations (``step`` / ``skillopt_step`` / ``gepa_val_gate``)
    with GEPA's locally-killed children (``gepa_local_gate`` with ``passed=False``),
    which are spent iterations that never reach the val gate. ``delta`` is
    ``val - parent_val``; when the event carries no ``parent_val`` (skillopt_step,
    single lineage) it is taken against the running best, which is that algorithm's
    actual parent.
    """
    gated = {id(e): e for e in _iteration_events(run_dir)}
    rows = []
    for rec in _raw_events(run_dir):
        if rec.get("kind") == _LOCAL_GATE_KIND and not rec.get("passed"):
            rows.append((rec.get("t") or 0.0, rec, True))
    for e in _iteration_events(run_dir):
        rows.append((e.get("t") or 0.0, e, False))
    rows.sort(key=lambda r: r[0])
    del gated

    out: list[dict] = []
    best = None
    for _t, ev, local in rows:
        cid = ev.get("candidate") or ev.get("candidate_id")
        if local:
            # Carry the real signed delta the event already holds instead of hardcoding
            # 0.0, so a tie is distinguishable from a regression in the series (review #7).
            # This cannot change deadness: gepa.py's pass condition is a strict
            # ``child_sum > parent_sum``, so every row reaching here already has Δ <= 0.
            # It is diagnostic information, not a new escape hatch.
            cs, ps = ev.get("child_sum"), ev.get("parent_sum")
            d = (float(cs) - float(ps)) if (cs is not None and ps is not None) else 0.0
            out.append({"candidate": cid, "parent": ev.get("parent"),
                        "accepted": False, "delta": d, "local": True})
            continue
        accepted = bool(ev.get("accept"))
        val = ev.get("val")
        val = float(val) if val is not None else None
        pv = ev.get("parent_val")
        base = float(pv) if pv is not None else best
        delta = (val - base) if (val is not None and base is not None) else 0.0
        new_best = bool(accepted and val is not None and (best is None or val > best))
        out.append({"candidate": cid, "parent": ev.get("parent"),
                    "accepted": accepted, "delta": delta, "local": False,
                    "val": val, "new_best": new_best})
        if val is not None and (best is None or val > best):
            best = val
    return out


def _dead(row: dict) -> bool:
    """A spent iteration that bought no progress.

    Alive = raised the global best, OR was a near-miss (rejected with Δ > 0 — the
    anti-false-positive class, which #113's t-correction enlarged). Everything else
    is dead, including an accept that did not top the incumbent best (best-val
    velocity 0). ``new_best`` is annotated by :func:`series`.
    """
    if row["accepted"]:
        return not row.get("new_best")   # accepted but not a new best -> velocity 0
    return row["delta"] <= 0.0           # rejected: a near-miss (Δ>0) is alive


def _lineage_dead(row: dict) -> bool:
    """Dead ground *for one parent* — a strictly narrower test than :func:`_dead`.

    An ACCEPT is never dead ground for a lineage, even when it did not top the global
    best. Widening the per-instance Pareto frontier *is* GEPA's mechanism
    (arXiv:2507.19457): a specialist child that clears the honest val gate is the most
    productive thing a lineage can produce. Reusing :func:`_dead` here marked a lineage
    whose children were ALL accepted as exhausted and dropped it from GEPA's sampling
    pool — steering the search away from its best region, with no ratchet on this path
    and no stop event to show for it.

    ``_dead``'s accepted-but-not-best clause stays at the GLOBAL level, where the
    zero-accept ratchet means such a streak can only ever reach ``diversify``. There is
    no ratchet per lineage, so the clause does not belong here.
    """
    return (not row["accepted"]) and row["delta"] <= 0.0


def exhausted_lineages(rows: list[dict], cfg: PlateauConfig) -> list[str]:
    """Parents whose last ``lineage_window`` children were all dead.

    Independent of the global level: GEPA can have one exhausted lineage while
    another is accepting every iteration. Uses :func:`_lineage_dead`, NOT :func:`_dead` —
    see that docstring for why an accept is never dead ground for a lineage.
    """
    by_parent: dict[str, list[dict]] = {}
    for r in rows:
        p = r.get("parent")
        if p:
            by_parent.setdefault(str(p), []).append(r)
    out = []
    for parent, children in by_parent.items():
        tail = children[-cfg.lineage_window:]
        if len(tail) >= cfg.lineage_window and all(_lineage_dead(c) for c in tail):
            out.append(parent)
    return sorted(out)


def assess(run_dir, cfg: PlateauConfig | None = None) -> PlateauState:
    """Read the run's event stream and decide the current escalation level."""
    cfg = cfg or PlateauConfig()
    rows = series(run_dir)
    if not rows:
        return PlateauState(reason="no iterations yet")

    run_length = 0
    accepts_in_streak = 0
    for r in reversed(rows):
        if _dead(r):
            run_length += 1
            if r["accepted"]:
                accepts_in_streak += 1
        else:
            break

    vals = [r["val"] for r in rows if r.get("val") is not None]
    best_val = max(vals) if vals else 0.0
    tail = rows[-cfg.window:]
    near = sum(1 for r in tail if (not r["accepted"]) and r["delta"] > 0.0)
    accepts = sum(1 for r in rows if r["accepted"])

    # The ratchet: any accept inside the streak caps escalation at `warn`. A run that is
    # still clearing the honest val gate every iteration is doing the thing it was built
    # to do — GEPA widening its per-instance Pareto frontier is exactly this shape — so it
    # gets a warning and nothing more: no behavioural prompt intervention, never a stop.
    # Only a streak with ZERO accepts may reach `diversify` or `stop`. That also keeps the
    # diversify prompt block honest: it can only ever fire on a streak that really did
    # fail, so it never tells the optimizer a lineage failed when it was accepting.
    if accepts_in_streak:
        level = "warn" if run_length >= cfg.warn_at else "ok"
    elif run_length >= cfg.stop_at and cfg.stop:
        level = "stop"
    elif run_length >= cfg.diversify_at:
        level = "diversify"
    elif run_length >= cfg.warn_at:
        level = "warn"
    else:
        level = "ok"

    if level == "ok":
        reason = (f"progressing: {run_length} dead iteration(s) in a row "
                  f"(< window {cfg.window}); {near} near-miss(es) in the last "
                  f"{len(tail)}, {accepts} accept(s) total")
    else:
        # Only claim "no near-miss" when the streak really contained neither a near-miss
        # nor an accept; otherwise the string contradicts its own ratchet clause.
        detail = ("; no near-miss in that streak" if accepts_in_streak == 0 else
                  f"; but {accepts_in_streak} accept(s) in the streak cap escalation at "
                  "warn (the gate is still passing — frontier still widening)")
        reason = (f"plateau: {run_length} consecutive iterations bought no new best val "
                  f"(warn {cfg.warn_at} / diversify {cfg.diversify_at} / "
                  f"stop {cfg.stop_at}){detail}")

    return PlateauState(
        level=level, run_length=run_length, iterations=len(rows), best_val=best_val,
        velocity=0.0 if run_length else best_val, near_misses=near, accepts=accepts,
        accepts_in_streak=accepts_in_streak,
        exhausted_lineages=exhausted_lineages(rows, cfg), reason=reason,
    )


def check(run_dir, cfg: PlateauConfig | None = None, *, last: PlateauState | None = None,
          algorithm: str = "") -> PlateauState:
    """``assess`` + emit events on change, so the terminal/dashboard can show it.

    ``plateau`` fires whenever the escalation level changes (including back to
    ``ok`` — a plateau that broke is news too). ``lineage_exhausted`` fires once per
    newly-exhausted parent.
    """
    st = assess(run_dir, cfg)
    prev_level = last.level if last else "ok"
    prev_ex = set(last.exhausted_lineages) if last else set()
    if st.level != prev_level:
        run_dir.log_event("plateau", algorithm=algorithm, **st.to_dict())
    for parent in st.exhausted_lineages:
        if parent not in prev_ex:
            run_dir.log_event("lineage_exhausted", algorithm=algorithm, parent=parent,
                              window=(cfg or PlateauConfig()).lineage_window,
                              plateau_level=st.level)
    return st


def prompt_block(st: PlateauState, *, max_ids: int = 6, max_id_chars: int = 60) -> str:
    """The escalation-level-1 intervention: a paradigm-shift block for the prompt.

    Empty string unless the level reached ``diversify``. This is *additive* to the
    algorithm's own prompt and to #129's rejected-approach constraints — those say
    "do not repeat these specific edits"; this says "the whole direction is dead,
    change strategy". Composed, they read as: avoid these, and do not just perturb
    them either.

    Deliberately does NOT list rejected candidate ids: #129/PR222 already injects the
    rejected approaches with their normalized signatures and reasons, which is strictly
    more informative than bare ids. One channel, one owner. (The old ``rejected=``
    parameter also called ``RejectedMemory.entries()``, which #199 removes — behind a
    bare ``except`` that swallowed the AttributeError, so the line silently vanished in
    the composed tree. Deleting it fixes the overlap and the silent loss at once.)

    Bounded: ``max_ids`` lineages, each truncated to ``max_id_chars``, so the block has a
    hard ceiling regardless of how many lineages a long GEPA run exhausts. The caller
    must still route the result through ``optimizer_context.cap_instructions`` (or
    ``render_instructions(extra=...)``) so the ASSEMBLED prompt is capped too.
    """
    if not st.should_diversify:
        return ""
    lines = [
        "",
        "## PLATEAU — CHANGE APPROACH (escalation: diversify)",
        f"The last {st.run_length} iterations bought no new best val: no near-misses, "
        "no movement in the direction that counts. Best val has not improved "
        f"({st.best_val:.3f}). Incrementally refining the current approach is not "
        "working and repeating it will spend the rest of the budget for nothing.",
        "REQUIRED this iteration: make a MATERIALLY DIFFERENT change, not a variation "
        "of the previous attempts. Pick a different mechanism (e.g. move a rule from "
        "prose into code, restructure rather than reword, attack a task cluster you "
        "have not touched, remove something instead of adding), and state in one line "
        "which prior approach you are abandoning and why the new one differs in kind.",
    ]
    if st.exhausted_lineages:
        shown = [str(p)[:max_id_chars] for p in st.exhausted_lineages[:max_ids]]
        more = len(st.exhausted_lineages) - len(shown)
        tail = f" (+{more} more)" if more > 0 else ""
        lines.append("Exhausted lineage(s) — every recent child of these was rejected with "
                     f"no improvement, treat them as dead ground: {', '.join(shown)}{tail}.")
    return "\n".join(lines) + "\n"


def _demo() -> None:
    """Self-check: a spiky-but-progressing run must NOT trigger; a dead one must."""
    import tempfile
    from pathlib import Path

    from .rundir import RunDir

    cfg = PlateauConfig(window=4, escalate_every=2)

    def build(steps):
        d = Path(tempfile.mkdtemp())
        rd = RunDir.create(d)
        prev = 0.0
        for accept, val in steps:
            rd.log_event("step", candidate=f"c{val}", accept=accept, val=val, parent_val=prev)
            if accept:
                prev = val
        return rd

    # Spiky but progressing: near-misses (Δ>0, sub-significant) then a breakthrough.
    spiky = build([(False, 0.05), (False, 0.08), (False, 0.06), (False, 0.09),
                   (False, 0.07), (False, 0.10), (True, 0.40)])
    assert assess(spiky, cfg).level == "ok", assess(spiky, cfg)

    # Dead: every child scores at or below its parent.
    dead = build([(False, 0.0)] * 8)
    st = assess(dead, cfg)
    assert st.level == "stop", st
    assert st.run_length == 8, st
    print("plateau self-check OK")


if __name__ == "__main__":
    _demo()
