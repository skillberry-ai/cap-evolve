"""Footprint detection — which val tasks an edit could causally have affected.

A candidate's edit touches a handful of named surfaces (a tool, a prompt section, a
function). The gate, though, measures its delta across EVERY val task, so every task the
edit cannot reach contributes pure measurement noise to the SE and buries the effect.
Measured on run_finalrun6 (7 candidates, 30 val tasks): SE(paired Δ) ran 0.022-0.035
while the real per-edit effects were 0.011-0.05, and the 7-way null-control replicate
spread (0.567-0.603) was statistically indistinguishable from the 7-way across-candidate
spread (0.570-0.607) — the measurement could not tell an edit from a re-measurement.

Restricting the delta vector to the tasks inside the edit's footprint is what fixes that:
a task the edit cannot reach has Δ=0 BY CONSTRUCTION, not by measurement, so it belongs
in the vector as a zero rather than as noise (see ``harness._paired_deltas``, which does
the zero-padding — the vector keeps its full length, so Δ̄ stays on the same scale as the
val reward while the SE stops being dominated by tasks the edit never touched).

Both steps here are deliberately dumb and generic — no benchmark, capability, agent or
optimizer shape is assumed:

  * ``touched_symbols`` reads the NAMED SURFACES out of a unified diff (whatever
    ``harness._diff_capabilities`` produced for this candidate): definitions, calls, and
    ``"name": "…"`` declarations on the changed lines, falling back per hunk to the
    enclosing definition when a hunk names nothing of its own. Not "every identifier" —
    most changed lines in a real capability edit are docstring prose, and its words match
    every rollout in the split.
  * ``in_footprint_tasks`` asks, per task, whether any of those names appears anywhere in
    the persisted rollout record. One flat substring search over the serialized rollout,
    rather than a walk of some particular trace schema: ``Rollout.tool_calls`` is the
    framework's only cross-adapter contract for "what the agent called", and adapters
    legitimately leave it empty while putting the same names in their own trace shape
    (harbor's tau2 rollouts do exactly this). The flat search reads both and cares about
    neither. A name that reaches almost every task is then dropped, because it localizes
    nothing — see ``_UBIQUITOUS_FRACTION``.

The search still OVER-includes, and that is the safe direction on purpose: over-including
gives back some of the noise the restriction removes, while under-including would zero out
a task the edit really did move and manufacture a gain out of a task that regressed. Every
failure mode degrades toward "no footprint", which callers read as "measure everything, as
before".

``footprint`` returns ``None`` — never a partial guess — whenever it cannot establish a
restriction worth applying: no diff, no surfaces, a diff so broad that its surface set is
meaningless, no rollouts on disk, or a footprint that covers every task anyway. A caller
that gets ``None`` falls back to the full delta vector, so nothing breaks when footprint
detection cannot determine a surface.

Measured on run_finalrun6's own rollouts, this is what the restriction does to the gate's
bar for each of the run's 7 candidates (no new rollouts spent)::

    cand_1  footprint None    SE 0.0222 -> 0.0222   (cross-cutting guard: no restriction)
    cand_2  footprint 18/30   SE 0.0250 -> 0.0193
    cand_3  footprint 13/30   SE 0.0276 -> 0.0208
    cand_4  footprint 14/30   SE 0.0244 -> 0.0159
    cand_5  footprint 11/30   SE 0.0318 -> 0.0255
    cand_6  footprint 16/30   SE 0.0313 -> 0.0262
    cand_7  footprint  4/30   SE 0.0346 -> 0.0046   (docstring-only edit to ONE tool)

Note what stays unrestricted: the candidate's recorded ``val`` reward is still the mean over
the WHOLE split, and so is every number the report and the val curve publish. The footprint
narrows only the vector the significance test's variance is computed from.
"""

from __future__ import annotations

import re
from pathlib import Path

#: NAMED SURFACES on a changed line, in three shapes — a definition (``def x`` / ``class X``
#: / ``function x``), a call (``x(``), and a declared name in a data file (``"name": "x"``,
#: which is how ``tools.json`` and most manifest formats spell a tool). Deliberately NOT
#: "every identifier": most changed lines in a real capability edit are docstring prose, and
#: the words in it ("cancelled", "flights", "upcoming", "user") match every rollout in the
#: split. Measured on run_finalrun6's cand_2 — a 1.7KB diff adding one tool — an
#: every-identifier extractor produced 67 symbols of which 60 were English; the surface
#: extractor produces the two that matter (``cancel_reservations``, ``cancel_reservation``).
#: NOTE the call arm has NO ``\s*`` before ``\(``. Prose puts a space before a parenthesis
#: ("more than one reservation cancelled (e.g. …)"); a call never does, in any language's
#: style. That one character is what stops docstring English from being read as a surface.
_SURFACE = re.compile(
    r"(?:\b(?:def|class|function|func|fn|sub|method)\s+([A-Za-z_][A-Za-z0-9_]{2,}))"
    r"|(?:\b([A-Za-z_][A-Za-z0-9_]{2,})\()"
    r"|(?:[\"']name[\"']\s*:\s*[\"']([^\"']{3,})[\"'])"
)

#: Definitions only, for the lines a hunk shows as CONTEXT rather than as changed — plus the
#: trailing section label on a ``@@`` header, which most diff tools fill with the enclosing
#: definition. An edit inside a function body (a docstring-only change, say) names no surface
#: on its own changed lines, and the enclosing definition IS its surface: run_finalrun6's
#: cand_7 rewrote one tool's docstring and would otherwise have had no footprint at all.
_ENCLOSING = re.compile(
    r"\b(?:def|class|function|func|fn|sub|method)\s+([A-Za-z_][A-Za-z0-9_]{2,})")

#: A symbol found in this fraction of the split's tasks or more is discarded before the
#: footprint is built. It localizes nothing — whatever it is (a shared exception type, a
#: helper every rollout touches, a common English word that survived the extractor), a
#: footprint containing it is the whole split. Adaptive rather than another stop-list: the
#: run's own rollouts say which names discriminate, and no hand-maintained word list has to
#: guess it per capability, language or benchmark.
_UBIQUITOUS_FRACTION = 0.8

#: Keywords and ubiquitous library names that take a call-shape and would otherwise be
#: extracted as surfaces. They appear in nearly every edit and name nothing specific to it.
_STOP = frozenset("""
append assert bool break case catch class const continue def defaultdict del dict elif
else enum except exception export extends filter finally float for foreach format from
func function get getattr goto hasattr if implements import in include index insert
instanceof int interface isinstance items join keys lambda len let list map max min new
next nil none not null object open or pass pop print property put raise range replace
return round self set setattr sorted split staticmethod str strip string struct sum super
switch throw throws try tuple type typeof union update use values var void while with
yield
""".split())


def touched_symbols(diff_text: str, *, max_symbols: int = 40) -> set[str]:
    """Named surfaces defined, called or declared on the changed (+/-) lines of a diff.

    ``max_symbols`` is a give-up threshold, not a truncation: a diff that names more distinct
    surfaces than this is a rewrite rather than a targeted edit, and its footprint would cover
    the split anyway. Returning the empty set makes the caller fall back to measuring
    everything, which is the honest answer for a rewrite.
    """
    out: set[str] = set()
    hunk: set[str] = set()          # surfaces named by THIS hunk's own changed lines
    enclosing: str | None = None    # nearest definition seen in context before them
    lines = list((diff_text or "").splitlines())

    def _close():
        # A hunk that named nothing of its own is an edit INSIDE something — its surface is
        # the enclosing definition. Only then, so a hunk that does name its surfaces cannot
        # drag in whatever else happens to sit within the diff's context window.
        out.update(hunk or ({enclosing} if enclosing else set()))

    for line in lines:
        if line[:3] in ("+++", "---"):
            continue
        if line.startswith("@@"):
            _close()
            hunk, enclosing = set(), None
            for m in _ENCLOSING.finditer(line):   # git-style section label, when present
                enclosing = m.group(1)
            continue
        if line[:1] in ("+", "-"):
            for m in _SURFACE.finditer(line[1:]):
                w = m.group(1) or m.group(2) or m.group(3)
                if w and w.lower() not in _STOP:
                    hunk.add(w)
        else:
            for m in _ENCLOSING.finditer(line):
                if m.group(1).lower() not in _STOP:
                    enclosing = m.group(1)        # nearest one wins
    _close()
    return set() if len(out) > max_symbols else out


def in_footprint_tasks(run_dir, tags, symbols, split: str = "val") -> set[str]:
    """Task ids whose persisted rollouts (under any of ``tags``) mention any symbol.

    Both sides' tags belong in ``tags``: an edit that ADDS a surface is exercised only in
    the candidate's rollouts, one that REMOVES a surface only in the parent's, and a task
    that either side routed through the edited surface is inside the footprint. The union
    is the conservative (over-including) choice, which is the direction that cannot
    manufacture a gain.
    """
    if not symbols:
        return set()
    d = Path(getattr(run_dir, "rollouts", run_dir)) / split
    if not d.is_dir():
        return set()
    symbols = set(symbols)
    # Which tasks each symbol reaches, counted per symbol rather than unioned as we go, so a
    # symbol that reaches nearly everything can be dropped before the union — see
    # _UBIQUITOUS_FRACTION.
    reach: dict[str, set[str]] = {s: set() for s in symbols}
    tasks: set[str] = set()
    for tag in tags:
        if not tag:
            continue
        for f in sorted(d.glob(f"*__{tag}__t*.json")):
            tid = f.name.split("__", 1)[0]
            tasks.add(tid)
            pending = [s for s in symbols if tid not in reach[s]]
            if not pending:
                continue          # every symbol already reaches this task
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for s in pending:
                if s in text:
                    reach[s].add(tid)
    if not tasks:
        return set()
    cap = _UBIQUITOUS_FRACTION * len(tasks)
    hit: set[str] = set()
    for s, ts in reach.items():
        if ts and len(ts) < cap:
            hit |= ts
    return hit


def footprint(run_dir, *, parent_dir, cand_dir, tags, split: str = "val",
              all_task_ids=None) -> set[str] | None:
    """The task ids a candidate's edit can causally reach — or ``None`` if unknowable.

    ``None`` means "no usable footprint data": the caller must measure the full split, the
    behaviour every run had before this existed. It is returned for a candidate whose diff
    is empty or too broad to localize, whose rollouts are not on disk, and — importantly —
    whose footprint turns out to cover every task that was measured, since restricting to
    everything is not a restriction and claiming one would be misleading.
    """
    from .harness import _diff_capabilities

    try:
        # A much higher cap than the optimizer-prompt default: this diff is read by a
        # regex, not by a human with a context window, and a truncated tail silently
        # drops the symbols that localize the edit.
        diff = _diff_capabilities(Path(parent_dir), Path(cand_dir), max_chars=400_000,
                                  context=12)
    except Exception:  # noqa: BLE001 — an unreadable snapshot means no footprint, not a crash
        return None
    symbols = touched_symbols(diff)
    if not symbols:
        return None
    tasks = in_footprint_tasks(run_dir, tags, symbols, split)
    if not tasks:
        return None
    if all_task_ids is not None and set(map(str, all_task_ids)) <= tasks:
        return None
    return tasks
