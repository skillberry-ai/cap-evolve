"""schema_v2 — emitters + backward-compat reader for Run schema v2 (issue #701).

The field contract lives in ``docs/RUN_SCHEMA_V2.md``; this module is the only code that
knows the enum values and required keys. Everything is additive and optional: emitters
never raise (a bad payload becomes a ``schema_warning`` event) and :func:`normalize_node`
fills fallbacks so a v1 run (no v2 keys) reads the same as a v2 one.
"""

from __future__ import annotations

import re

EVAL_STATES = ("unevaluated", "screened", "partial", "full")  # monotone order
DECISIONS = ("propose", "screen", "promote", "kill", "merge", "grow", "accept", "reject",
             "stop", "tradeoff")
PARENT_ROLES = ("primary", "donor")

#: kind -> keys that must be present (not None) in the payload.
REQUIRED = {
    "candidate_proposed": ("id", "parents"),
    "eval_coverage": ("tag", "split", "task_ids", "trials"),
    "eval_state": ("id", "to"),
    "decision": ("id", "decision"),
    "optimizer_spend": ("role", "usd"),
}

_SCREEN_SUFFIX = re.compile(r"__screen\d+$")


def emit(run_dir, kind: str, **fields) -> bool:
    """Log a v2 event; never raises. Returns False (and logs ``schema_warning``) if the
    payload misses a required key or carries an out-of-enum value."""
    try:
        bad = [k for k in REQUIRED.get(kind, ()) if fields.get(k) is None]
        if kind == "decision" and fields.get("decision") not in DECISIONS:
            bad.append("decision")
        if kind == "eval_state" and fields.get("to") not in EVAL_STATES:
            bad.append("to")
        if bad:
            run_dir.log_event("schema_warning", of=kind, bad_keys=sorted(set(bad)))
            return False
        run_dir.log_event(kind, **fields)
        return True
    except Exception:  # noqa: BLE001 — telemetry must never fail an evaluation
        return False


def advance_eval_state(run_dir, node: dict | None, tag: str, to: str) -> bool:
    """Emit ``eval_state {id, from, to}`` only when ``to`` is later than the node's current
    state (unevaluated < screened < partial < full). ``node`` is the tag's latest graph
    record (or None). Read-then-emit: callers racing on one tag must serialise themselves
    (``graph.append_node_locked``, #714)."""
    cur = normalize_node(node or {})["eval_state"]
    if to not in EVAL_STATES or EVAL_STATES.index(to) <= EVAL_STATES.index(cur):
        return False
    return emit(run_dir, "eval_state", id=tag, to=to, **{"from": cur})


def coverage_state(task_ids, val_ids, trials: int, min_trials: int = 1) -> str:
    """``full`` when every val task (ids outside the val split ignored) ran with
    >= ``min_trials`` trials, else ``partial``."""
    val = set(val_ids)
    return "full" if val and val <= set(task_ids) and trials >= min_trials else "partial"


def legacy_coverage(events, val_ids) -> dict[str, dict]:
    """``{candidate_tag: {task_ids, trials_min, trials_max, screen_only}}`` from v1
    ``eval_start``/``evaluate`` val events. A ``subset_ids`` evaluate covers only that
    subset; an unsubsetted one covers the whole val split. ``<tag>__screenN`` folds into
    ``<tag>`` and marks it screen-only until a non-screen eval is seen."""
    trials: dict[str, int] = {}
    out: dict[str, dict] = {}
    for e in events:
        if e.get("split") != "val":
            continue
        raw = e.get("tag")
        if e.get("kind") == "eval_start":
            trials[raw] = e.get("n_trials") or 1
        elif e.get("kind") == "evaluate":
            base = _SCREEN_SUFFIX.sub("", raw or "")
            c = out.setdefault(base, {"task_ids": set(), "trials": [], "screen_trials": []})
            c["task_ids"] |= set(e.get("subset_ids") or val_ids)
            c["screen_trials" if base != raw else "trials"].append(trials.get(raw, 1))
    # trials describe the real evals; screen trials only stand in for a screen-only node
    return {t: {"task_ids": sorted(c["task_ids"]), "trials_min": min(c["trials"] or c["screen_trials"]),
                "trials_max": max(c["trials"] or c["screen_trials"]), "screen_only": not c["trials"]}
            for t, c in out.items()}


def normalize_node(node: dict, *, val_ids=None, evals: dict | None = None,
                   parents: list[str] | None = None) -> dict:
    """Return a copy of a graph node with v2 keys filled from legacy fields.

    ``evals`` (from :func:`legacy_coverage`) and ``val_ids`` give real evaluated-task
    coverage: all val tasks -> ``full``; a screen only -> ``screened``; else ``partial``.
    Without them, ``val_mean`` alone is NOT proof of a full eval: a node with a ``screen``
    and no ``gate`` row was screen-killed and reads ``screened`` (cand_9 in the recorded run).
    ``status: queued`` maps to ``proposed``. ``parents`` overrides the node's own list (pass
    ``CandidateGraph.parents_of`` output); self-parents are dropped. ``base_for_eval``
    defaults to the first parent; ``parent_roles`` marks it primary and the rest donor.
    An explicit ``eval_state``/``coverage`` always wins.
    """
    n = dict(node)
    pl = [p for p in (parents if parents is not None else n.get("parents") or [])
          if p != n.get("id")]
    if n.get("status") == "queued":
        n["status"] = "proposed"
    cov = (evals or {}).get(n.get("id"))
    if not n.get("eval_state"):
        if cov and val_ids is not None:
            full = coverage_state(cov["task_ids"], val_ids, cov["trials_min"]) == "full"
            n["eval_state"] = ("full" if full and not cov["screen_only"] else
                               "screened" if cov["screen_only"] else "partial")
        elif n.get("val_mean") is not None and (n.get("gate") or not n.get("screen")):
            n["eval_state"] = "full"
        elif n.get("screen") or n.get("subset"):
            n["eval_state"] = "screened"
        else:
            n["eval_state"] = "unevaluated"
    if pl:
        n.setdefault("base_for_eval", pl[0])
        n.setdefault("parent_roles", {p: ("primary" if i == 0 else "donor")
                                      for i, p in enumerate(pl)})
    if not n.get("coverage") and n["eval_state"] != "unevaluated":
        if cov:
            ids, tmin, tmax = cov["task_ids"], cov["trials_min"], cov["trials_max"]
        else:
            ids = (n.get("subset") or {}).get("task_ids") or (n.get("screen") or {}).get("subset_ids")
            tmin = tmax = None
        if ids:
            n["coverage"] = {"split": "val", "task_ids": list(ids), "n_tasks": len(ids),
                             "n_val_tasks": len(val_ids) if val_ids is not None else None,
                             "trials_min": tmin, "trials_max": tmax,
                             "full": n["eval_state"] == "full"}
    return n
