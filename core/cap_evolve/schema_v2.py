"""schema_v2 — emitters + backward-compat reader for Run schema v2 (issue #701).

The field contract lives in ``docs/RUN_SCHEMA_V2.md``; this module is the only code that
knows the enum values and required keys. Everything is additive and optional: emitters
never raise (a bad payload becomes a ``schema_warning`` event) and :func:`normalize_node`
fills fallbacks so a v1 run (no v2 keys) reads the same as a v2 one.
"""

from __future__ import annotations

SCHEMA_VERSION = 2

EVAL_STATES = ("unevaluated", "screened", "partial", "full")  # monotone order
NODE_STATUSES = ("queued", "screened", "proposed", "superseded", "gated", "accepted", "rejected")
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
    state (monotone: unevaluated < screened < partial < full). ``node`` is the tag's latest
    graph record (or None)."""
    cur = normalize_node(node or {})["eval_state"]
    if to not in EVAL_STATES or EVAL_STATES.index(to) <= EVAL_STATES.index(cur):
        return False
    return emit(run_dir, "eval_state", id=tag, to=to, **{"from": cur})


def coverage_state(task_ids, n_val_tasks: int, trials: int, min_trials: int = 1) -> str:
    """``full`` when every val task was run with >= ``min_trials``, else ``partial``."""
    return "full" if len(set(task_ids)) >= n_val_tasks and trials >= min_trials else "partial"


def normalize_node(node: dict) -> dict:
    """Return a copy of a graph node with v2 keys filled from legacy fields.

    ``eval_state``: explicit value wins; else ``status: queued`` -> ``unevaluated``;
    ``val_mean`` present -> ``full``; a screen or subset -> ``screened``; else
    ``unevaluated``. ``base_for_eval`` defaults to ``parents[0]``; ``parent_roles`` marks
    ``parents[0]`` primary and the rest donor; ``eval_coverage`` is derived from the screen
    subset when a node was only screened. Other absent keys stay absent.
    """
    n = dict(node)
    parents = n.get("parents") or []
    if not n.get("eval_state"):
        if n.get("status") == "queued":
            state = "unevaluated"
        elif n.get("val_mean") is not None:
            state = "full"
        elif n.get("screen") or n.get("subset"):
            state = "screened"
        else:
            state = "unevaluated"
        n["eval_state"] = state
    if parents:
        n.setdefault("base_for_eval", parents[0])
        n.setdefault("parent_roles", {p: ("primary" if i == 0 else "donor")
                                      for i, p in enumerate(parents)})
    if not n.get("eval_coverage") and n["eval_state"] == "screened":
        ids = (n.get("subset") or {}).get("task_ids") or (n.get("screen") or {}).get("subset_ids")
        if ids:
            n["eval_coverage"] = {"split": "val", "task_ids": list(ids), "n_tasks": len(ids),
                                  "full": False}
    return n
