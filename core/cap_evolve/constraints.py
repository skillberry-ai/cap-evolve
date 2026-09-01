"""Free-text ``stop_condition`` → concrete, re-checkable predicates.

``stop_condition`` in ``capevolve.yaml`` is prose, written by a human at intake:

    "reach val mean >= 0.75, or stop after $40 / 90 minutes; don't regress task 12"

Prose is the right *input* — it is how people actually state a budget — but it is a
terrible thing for a loop to enforce, because an agent "remembering" the constraint
across many turns is exactly how a $6.00 cap becomes $6.01 and a "90 minutes" run
takes three hours. So we normalize it ONCE into predicates and then re-check those
predicates against the run dir's persisted spend every round.

Two functions, both pure and stdlib-only:

  * :func:`parse_constraints` — text → ``{"predicates": [...], "ambiguous": [...],
    "unenforceable": [...], "text": "<verbatim>"}``. The original prose is always carried
    alongside, because a parser that silently drops half a sentence is worse than no
    parser. ``unenforceable`` is a clause-level list of prose this parser recognized NO
    numeric/task-protection pattern in at all (a behavioral instruction like "use
    screen.py before paying for full val") — distinct from ``ambiguous``, which is a
    number this parser SAW but could not resolve (no unit, vague magnitude).
  * :func:`check_constraints` — predicates + measured actuals → per-predicate
    satisfied/violated + one ``stop | continue | narrow_scope`` recommendation.

**Ambiguity is reported, never guessed.** A phrase like "don't spend too much" or a
bare number with no unit produces an entry in ``ambiguous`` with the exact span, so the
agent asks the user instead of inventing a ceiling. An unparsed constraint is NOT
treated as "no constraint": ``check_constraints`` surfaces the ambiguity list in its
payload so the caller can refuse to run unattended.
"""

from __future__ import annotations

import re

__all__ = ["parse_constraints", "check_constraints", "cost_target"]

#: Recognized kinds. ``max_*`` are ceilings (violated when actual >= target);
#: ``target_val_score`` is a goal (satisfied when actual >= target).
_CEILINGS = ("max_usd", "max_wallclock_seconds", "max_iterations", "max_stall",
             "max_metric_calls")

_TIME_UNITS = {
    "s": 1.0, "sec": 1.0, "secs": 1.0, "second": 1.0, "seconds": 1.0,
    "m": 60.0, "min": 60.0, "mins": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hrs": 3600.0, "hour": 3600.0, "hours": 3600.0,
}

# Vague cost/time/quality words that look like a constraint but carry no number.
_VAGUE = ("too much", "too long", "reasonable", "cheap", "cheaply", "quickly",
          "as soon as", "as good as possible", "best possible", "a while",
          "not too", "soon", "asap", "affordable", "low cost")

#: A number, WITH optional thousands separators. The grouped alternative must come
#: FIRST: regex alternation is ordered, so a bare ``\d+`` would match "1" of "1,200"
#: and stop at the comma. That is not a cosmetic miss — ``"$1,200"`` parsed as
#: ``max_usd=1.0`` and ``"2,000 USD"`` as ``max_usd=0.0`` (the bare pattern matched the
#: trailing "000"), and a $0 ceiling makes ``budget_exhausted()`` true before the first
#: rollout, killing the run with a message that blames spend instead of parsing. Worse,
#: it was a CONFIDENT wrong number: nothing landed in ``ambiguous``.
_NUM = r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"

#: Qualifiers that make a money figure a PER-ITERATION cap, not a total.
_PER_ITER = re.compile(r"^\s*(?:/|per|each|a|an)\s*(?:iteration|iter|round|step|candidate)\b"
                       r"|^\s*/\s*(?:iter|round)\b", re.I)


def _f(num: str) -> float:
    """Grouped digits -> float. ``"1,500.50"`` -> ``1500.5``."""
    return float(str(num).replace(",", ""))


def _add(preds: list, kind: str, target: float, op: str, span: str) -> None:
    preds.append({"kind": kind, "op": op, "target": float(target), "source": span.strip()})


def _split_qualified_msg(span: str, split: str) -> str:
    """Why a score goal naming train/test is REPORTED instead of installed."""
    return (f"{span.strip()!r} is qualified by {split!r}, but a score goal is only ever "
            "checked against the FULL-VAL mean (acceptance is val-only). State the val "
            f"bar here and track the {split} number separately, or say which you meant.")


def parse_constraints(text: str | None) -> dict:
    """Normalize a free-text stop condition into predicates + an ambiguity list.

    Recognized, case-insensitively:

    ==========================  ==========================================
    prose                       predicate
    ==========================  ==========================================
    ``val mean >= 0.75``,       ``target_val_score >= 0.75``
    ``score of 0.75``, ``75%``
    ``$40``, ``40 USD``         ``max_usd <= 40``
    ``90 minutes``, ``2h``      ``max_wallclock_seconds <= 5400``
    ``5 iterations``            ``max_iterations <= 5``
    ``3 rejects in a row``      ``max_stall <= 3``
    ``200 rollouts``            ``max_metric_calls <= 200``
    ``don't regress task 12``   ``protect_task == "12"``
    ==========================  ==========================================

    When the same ceiling appears twice, the TIGHTEST (smallest) wins — a stop
    condition is a promise about the worst case. Duplicate score targets keep the
    HIGHEST, for the same reason read the other way.
    """
    raw = text or ""
    t = raw.lower()
    preds: list = []
    ambiguous: list = []

    # --- score goal ---------------------------------------------------------
    # The cue set must cover how people ACTUALLY state the primary goal. "reach 90% on
    # val" worked only because of the '%'; "val reaches 0.85" and "Target: 0.7" — the two
    # most natural phrasings — fell through to the unitless-number branch, so the loop
    # had no idea what success was. Hence: `target`/`goal` are cues, and `reaches`/`hits`/
    # `:`/`=` are accepted connectors between the cue and the number.
    _CUE = (r"(?:val(?:idation)?\s*(?:mean|score|reward)?|score|reward|mean|accuracy"
            r"|pass\s*rate|target|goal)")
    _CONN = (r"(?:of|is|at\s*least|reach(?:es|ed|ing)?|hits?|gets?\s*to|achieves?"
             r"|[:=]|>=|=>|>|≥)?")
    # A score goal QUALIFIED BY ANOTHER SPLIT is not a val goal. ``target_val_score`` is
    # only ever checked against the FULL-VAL mean (honesty invariant 1: acceptance and
    # the score goal are val-only), so parsing "train mean >= 0.9" into it would enforce
    # a val bar while telling the user their train bar was being watched — a confidently
    # wrong number, which is the failure mode this module exists to avoid. Report it.
    # The qualifier can sit on EITHER side of the number: "train mean >= 0.9" and
    # "90% on the test split" are both non-val goals.
    _SPLIT_BEFORE = re.compile(r"\b(train(?:ing)?|test|held[\s-]*out)\s*(?:set|split)?\s*$")
    _SPLIT_AFTER = re.compile(r"^\s*(?:on|of|over|for)?\s*(?:the\s*)?"
                              r"(train(?:ing)?|test|held[\s-]*out)\b")
    for m in re.finditer(_CUE + r"\s*" + _CONN + r"\s*" + _NUM + r"\s*(%?)", t):
        v = _f(m.group(1))
        if m.group(2) == "%" or v > 1.0:
            v = v / 100.0
        if not (0.0 < v <= 1.0):
            continue
        qual = _SPLIT_BEFORE.search(t[:m.start()]) or _SPLIT_AFTER.match(t[m.end():])
        if qual:
            ambiguous.append(_split_qualified_msg(m.group(0), qual.group(1)))
            continue
        _add(preds, "target_val_score", v, ">=", m.group(0))
    if not any(p["kind"] == "target_val_score" for p in preds):
        for m in re.finditer(r"(?:reach(?:es|ed)?|hits?|gets?\s*to|achieves?|until)\s*"
                             + _NUM + r"\s*(%?)", t):
            v = _f(m.group(1))
            if m.group(2) == "%" or v > 1.0:
                v = v / 100.0
            if not (0.0 < v <= 1.0):
                continue
            # Same split-qualifier veto as the cued branch above — "reach 90% on the
            # test split" must not install a VAL bar.
            qual = _SPLIT_BEFORE.search(t[:m.start()]) or _SPLIT_AFTER.match(t[m.end():])
            if qual:
                ambiguous.append(_split_qualified_msg(m.group(0), qual.group(1)))
                continue
            _add(preds, "target_val_score", v, ">=", m.group(0))

    # --- money --------------------------------------------------------------
    # A money figure has a SCOPE, and prose routinely names both scopes in one breath
    # ("$5 per iteration but no more than $60 total"). Installing the per-iteration
    # figure as the total silently replaces a $60 budget with a $5 one, so the scope is
    # read from the words that FOLLOW the amount: a per-iteration qualifier routes to
    # `max_usd_per_iteration` (reported, but enforced by the spec's
    # `optimizer_usd_per_iter`, not by this loop's total), everything else is a total.
    def _money(m: "re.Match") -> None:
        tail = t[m.end():m.end() + 24]
        kind = "max_usd_per_iteration" if _PER_ITER.search(tail) else "max_usd"
        span = m.group(0) + (tail.split(",")[0].rstrip() if kind != "max_usd" else "")
        _add(preds, kind, _f(m.group(1)), "<=", span)

    for m in re.finditer(r"\$\s*" + _NUM, t):
        _money(m)
    for m in re.finditer(_NUM + r"\s*(?:usd|dollars?|bucks?)\b", t):
        _money(m)

    # --- time ---------------------------------------------------------------
    for m in re.finditer(_NUM + r"\s*(" + "|".join(sorted(_TIME_UNITS, key=len, reverse=True)) + r")\b", t):
        # Only treat a bare "m"/"h"/"s" as time when it is glued to the number
        # ("90m"), never when it is a stray word.
        unit = m.group(2)
        if len(unit) <= 1 and m.group(0)[len(m.group(1))] == " ":
            continue
        _add(preds, "max_wallclock_seconds", float(m.group(1)) * _TIME_UNITS[unit], "<=", m.group(0))

    # --- counters -----------------------------------------------------------
    for m in re.finditer(_NUM + r"\s*(?:iterations?|iters?|rounds?)\b", t):
        _add(preds, "max_iterations", float(m.group(1)), "<=", m.group(0))
    for m in re.finditer(_NUM + r"\s*(?:consecutive\s*)?(?:rejects?|rejections?|stall(?:s|ed)?|"
                         r"no-?improvements?)(?:\s*in\s*a\s*row)?\b", t):
        _add(preds, "max_stall", float(m.group(1)), "<=", m.group(0))
    for m in re.finditer(_NUM + r"\s*(?:rollouts?|metric\s*calls?|evals?|evaluations?)\b", t):
        _add(preds, "max_metric_calls", float(m.group(1)), "<=", m.group(0))

    # --- protected tasks ----------------------------------------------------
    for m in re.finditer(r"(?:do\s*n[o']?t|don't|never|must\s*not)\s*(?:regress|break|lose|worsen)\s*"
                         r"(?:task|tasks|id|ids)?\s*([\w.,\s-]{1,60})", t):
        for tid in re.split(r"[,\s]+", m.group(1).strip()):
            tid = tid.strip(".,;")
            if tid and tid not in ("any", "anything", "the", "a", "and", "or", "task", "tasks"):
                preds.append({"kind": "protect_task", "op": "==", "target": tid,
                              "source": m.group(0).strip()})

    # --- ambiguity ----------------------------------------------------------
    for phrase in _VAGUE:
        if phrase in t:
            ambiguous.append({"span": phrase,
                              "why": "vague magnitude — no number/unit to check against"})
    # A number with no recognized unit anywhere near it.
    claimed = set()
    for p in preds:
        claimed.update(re.findall(_NUM, str(p.get("source", ""))))
    for m in re.finditer(_NUM, t):
        if m.group(1) not in claimed:
            ambiguous.append({"span": raw[max(0, m.start() - 15):m.end() + 15].strip(),
                              "why": f"the number {m.group(1)!r} has no recognized unit "
                                     "(money/time/score/count) — say which it is"})
    if re.search(r"\band\b", t) and re.search(r"\bor\b", t) and len(preds) > 2:
        ambiguous.append({"span": raw.strip()[:160],
                          "why": "mixes 'and' with 'or' — the boolean structure of the "
                                 "stop rule is unclear; every predicate is treated "
                                 "independently (any ceiling stops, the score goal stops)"})
    if raw.strip() and not preds:
        ambiguous.append({"span": raw.strip()[:160],
                          "why": "no checkable predicate found — the loop cannot enforce "
                                 "this; ask the user for a number + unit"})
    # A per-iteration cap with no total is not a total budget. Say so rather than let the
    # caller assume the run is bounded: this loop only enforces totals.
    if (any(p["kind"] == "max_usd_per_iteration" for p in preds)
            and not any(p["kind"] == "max_usd" for p in preds)):
        ambiguous.append({"span": next(p["source"] for p in preds
                                       if p["kind"] == "max_usd_per_iteration"),
                          "why": "a PER-ITERATION $ cap was given but no TOTAL — this loop "
                                 "enforces totals, so the run is effectively unbounded in $. "
                                 "Ask for a total, or set max_usd in the spec"})

    # --- unenforceable prose -------------------------------------------------
    # A clause with a NUMBER but no recognized unit is already loud (the "no recognized
    # unit" branch above). A clause with NO number at all — a behavioral instruction like
    # "use screen.py before paying for full val each round" — matches none of the numeric/
    # protection patterns above and was, until now, silently dropped: neither enforced nor
    # reported, so a driver had no way to tell "the framework checked this and it's fine"
    # from "the framework never saw this at all". Purely mechanical: split on clause
    # boundaries and report any clause none of the predicates/ambiguous entries above were
    # extracted from — never an attempt to enforce the prose itself.
    _covered = [str(p.get("source", "")).lower() for p in preds] + \
        [str(a.get("span", "")).lower() for a in ambiguous if isinstance(a, dict)]
    unenforceable: list = []
    for clause in re.split(r"[;,.]\s+|\s+\band\b\s+|\s+\bor\b\s+", raw.strip()):
        clause = clause.strip().strip(".,;")
        if len(clause) < 8:  # too short to be a real, checkable instruction
            continue
        cl = clause.lower()
        if any(span and span in cl for span in _covered):
            continue
        if clause not in unenforceable:
            unenforceable.append(clause)

    # Tighten duplicates.
    out: list = []
    seen: dict = {}
    for p in preds:
        k = p["kind"]
        if k == "protect_task":
            key = (k, p["target"])
            if key in seen:
                continue
            seen[key] = True
            out.append(p)
            continue
        if k in seen:
            prev = seen[k]
            better = (p["target"] > prev["target"]) if k == "target_val_score" \
                else (p["target"] < prev["target"])
            if better:
                prev.update(p)
            continue
        seen[k] = p
        out.append(p)

    return {"text": raw, "predicates": out, "ambiguous": ambiguous,
            "unenforceable": unenforceable}


def cost_target(target: float, per_task_ceiling: dict) -> dict:
    """Cost a ``target_val_score`` against measured per-task headroom before accepting it.

    ``per_task_ceiling`` maps ``task_id -> highest rate that task can structurally reach``
    (e.g. ``min(0.95, measured_component_cap)`` — a task whose COMMUNICATE component rate
    measures 0.667 cannot reach 1.0 no matter what a capability edit does). The costed
    ceiling is the mean of those caps, i.e. ``1 - sum(1 - ceiling_t) / n``: the score no
    capability edit can exceed. A target above it is not a capability problem and should be
    renegotiated with the user rather than chased with more iterations.

    Motivating case: docs/TAU2_SUMMARY.md's own ceiling analysis found a ≈0.92 ceiling set by
    three tasks capped by things no edit could touch (a leaking user simulator, two
    COMMUNICATE-component rates) — two points of slack a 90%-target run had no way to close.
    """
    if not per_task_ceiling:
        return {"target": float(target), "feasible": None,
                "reason": "no per-task ceiling data — cannot cost this target"}
    ceiling = sum(per_task_ceiling.values()) / len(per_task_ceiling)
    feasible = float(target) <= ceiling + 1e-9
    return {
        "target": float(target),
        "costed_ceiling": round(ceiling, 4),
        "headroom": round(ceiling - float(target), 4),
        "feasible": feasible,
        "reason": (
            f"target {float(target):.4f} is "
            f"{'within' if feasible else 'ABOVE'} the costed ceiling {ceiling:.4f} "
            f"(mean of {len(per_task_ceiling)} per-task caps) — "
            + ("reachable by a capability edit" if feasible else
               "NOT reachable by any capability edit; renegotiate the target or the caps "
               "before spending more budget chasing it")
        ),
    }


def check_constraints(
    parsed: dict,
    *,
    best_val: float | None = None,
    usd: float = 0.0,
    wallclock_seconds: float = 0.0,
    iterations: int = 0,
    stall: int = 0,
    metric_calls: int = 0,
    regressed_tasks: list | None = None,
    warn_frac: float = 0.8,
    per_task_ceiling: dict | None = None,
) -> dict:
    """Check every parsed predicate against MEASURED actuals from the run dir.

    Returns ``{"predicates": [...], "recommendation", "reasons", "ambiguous",
    "remaining"}``:

      * a ceiling is ``violated`` when ``actual >= target`` — the same ``>=`` the
        run dir's ``budget_exhausted()`` uses, so the two can never disagree;
      * ``target_val_score`` is ``satisfied`` when the FULL-VAL mean reaches it
        (a subset screen can never satisfy a score goal);
      * ``protect_task`` is ``violated`` when the task appears in ``regressed_tasks``.

    Recommendation:
      ``stop``          — a ceiling is violated, or the score goal is met;
      ``narrow_scope``  — some ceiling is ≥ ``warn_frac`` consumed but the goal is not
                          met: there is budget for a cheap, targeted round, not for a
                          wide fan-out;
      ``continue``      — room left, goal unmet.
    """
    actual_of = {
        "max_usd": float(usd),
        "max_wallclock_seconds": float(wallclock_seconds),
        "max_iterations": float(iterations),
        "max_stall": float(stall),
        "max_metric_calls": float(metric_calls),
    }
    regressed = {str(t) for t in (regressed_tasks or [])}
    rows: list = []
    remaining: dict = {}
    stop_reasons: list = []
    warn_reasons: list = []

    for p in parsed.get("predicates") or []:
        kind = p["kind"]
        if kind in _CEILINGS:
            actual = actual_of[kind]
            target = float(p["target"])
            violated = actual >= target
            frac = (actual / target) if target > 0 else 0.0
            remaining[kind] = max(0.0, target - actual)
            rows.append({**p, "actual": actual, "violated": violated,
                         "satisfied": not violated, "consumed_frac": round(frac, 4)})
            if violated:
                stop_reasons.append(f"{kind} ceiling reached ({actual:.4g} >= {target:.4g})")
            elif frac >= warn_frac:
                warn_reasons.append(f"{kind} {frac * 100:.0f}% consumed "
                                    f"({actual:.4g}/{target:.4g})")
        elif kind == "target_val_score":
            actual = None if best_val is None else float(best_val)
            met = actual is not None and actual >= float(p["target"]) - 1e-9
            row = {**p, "actual": actual, "satisfied": met, "violated": False,
                   "note": "checked on the FULL-val mean only; a subset screen "
                           "can never satisfy this"}
            if per_task_ceiling:
                cost = cost_target(float(p["target"]), per_task_ceiling)
                row["cost"] = cost
                if cost.get("feasible") is False:
                    warn_reasons.append(
                        f"target_val_score {p['target']:.4f} is above the costed ceiling "
                        f"{cost['costed_ceiling']:.4f} — not reachable by any capability edit")
            rows.append(row)
            if met:
                stop_reasons.append(f"score goal met on full val "
                                    f"({actual:.4f} >= {p['target']:.4f})")
        elif kind == "max_usd_per_iteration":
            # Reported, never enforced here: a per-iteration cap belongs to the optimizer
            # invocation (the spec's `optimizer_usd_per_iter`). Presenting it as satisfied
            # would claim a check this function does not perform.
            rows.append({**p, "actual": None, "satisfied": None, "violated": False,
                         "note": "PER-ITERATION cap — not a total; enforced by the spec's "
                                 "optimizer_usd_per_iter, not by this check"})
        elif kind == "protect_task":
            hit = str(p["target"]) in regressed
            rows.append({**p, "actual": str(p["target"]) if hit else None,
                         "satisfied": not hit, "violated": hit})
            if hit:
                stop_reasons.append(f"protected task {p['target']!r} regressed")

    rec = "stop" if stop_reasons else ("narrow_scope" if warn_reasons else "continue")
    return {
        "predicates": rows,
        "remaining": remaining,
        "recommendation": rec,
        "reasons": stop_reasons or warn_reasons,
        "ambiguous": parsed.get("ambiguous") or [],
        "unenforceable": parsed.get("unenforceable") or [],
        "stop_condition_text": parsed.get("text", ""),
    }
