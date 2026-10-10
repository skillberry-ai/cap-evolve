"""dashboard_views -- Run schema v2 view fields for the dashboard reducer (issue #702).

``dashboard.reduce_run`` calls :func:`enrich` once. It annotates the events-reconstructed
nodes with ``eval_state`` / ``coverage`` / ``vs_parent`` / ``matched_task_ids`` /
``decisions`` and the pass-through v2 keys, using ``schema_v2.normalize_node`` so a run
with no v2 fields (an old run) still gets honest values: ``cand_9`` of the recorded
run_20261008_150326 reads ``screened`` with 8 of 30 tasks. Field names are the contract in
``docs/RUN_SCHEMA_V2.md``. Never raises into the reducer's caller on a malformed node.
"""

from __future__ import annotations

import json

from . import schema_v2
from .candidate_graph import CandidateGraph

#: v2 node keys copied through unchanged when the graph record carries them.
PASSTHROUGH = ("merge_base", "parent_roles", "branch_id", "base_for_eval", "stage", "edit",
               "capability_hash", "capability_files", "objectives", "vs_parent",
               "gate_verdict", "cost_ledger")
_LEGACY_DECISION = {"accept": "accept", "reject": "reject"}


def _val_ids(run_root, nodes) -> list[str]:
    try:
        v = json.loads((run_root / "splits.json").read_text(encoding="utf-8")).get("val")
        if v:
            return [str(x) for x in v]
    except (OSError, ValueError, AttributeError):
        pass
    return list((nodes.get("seed") or {}).get("per_task") or {})


def decisions(events) -> list[dict]:
    """Optimizer decisions in event order: v2 ``decision`` events, plus legacy
    ``accept``/``reject`` commits for candidates that have no v2 decision."""
    out = [{"t": e.get("t"), "id": e.get("id"), "decision": e.get("decision"),
            "evidence": e.get("evidence") or {}, "rationale": e.get("rationale"),
            "optimizer_usd": e.get("optimizer_usd")}
           for e in events if e.get("kind") == "decision"]
    have = {d["id"] for d in out}
    for e in events:
        cid = e.get("candidate") or e.get("tag")
        kind = ("accept" if e.get("accept") else "reject") if e.get("kind") == "step" else e.get("kind")
        if kind in _LEGACY_DECISION and cid and cid not in have:
            out.append({"t": e.get("t"), "id": cid, "decision": _LEGACY_DECISION[kind],
                        "evidence": {}, "rationale": e.get("reason"), "optimizer_usd": None})
            have.add(cid)
    return sorted(out, key=lambda d: d["t"] or 0)


def enrich(run_dir, nodes: dict[str, dict], events: list[dict]) -> list[dict]:
    """Annotate ``nodes`` in place; return the run-level decisions list."""
    try:
        val_ids = _val_ids(run_dir.root, nodes)
        evals = schema_v2.legacy_coverage(events, val_ids)
        g = CandidateGraph.load(run_dir)
        decs = decisions(events)
    except Exception:  # noqa: BLE001 -- unreadable graph/events: serve the v1 view
        return []
    for nid, n in nodes.items():
        try:
            _enrich_node(nid, n, g, nodes, val_ids, evals, decs)
        except Exception as e:  # noqa: BLE001 -- a malformed record must not break the reducer
            n.setdefault("eval_state", None)
            n["schema_warning"] = {"of": "dashboard_views", "error": f"{type(e).__name__}: {e}"}
    return decs


def _enrich_node(nid, n, g, nodes, val_ids, evals, decs) -> None:
    gn = g.node(nid) or {}
    # events-reconstructed nodes have no graph record on old runs: stand one in from them
    base = {"id": nid, "val_mean": n.get("val"), "status": n.get("status"),
            "parents": [n["parent"]] if n.get("parent") else [], **gn}
    if nid == "seed":
        base["val_mean"] = n.get("val")
    v2 = schema_v2.normalize_node(base, val_ids=val_ids, evals=evals,
                                  parents=g.parents_of(nid) or base["parents"])
    n["eval_state"] = v2["eval_state"]
    n["coverage"] = v2.get("coverage")
    n["parents"] = [p for p in v2.get("parents") or [] if p != nid]
    for k in PASSTHROUGH:
        if v2.get(k) is not None:
            n[k] = v2[k]
    cm = ((n.get("vs_parent") or {}).get("cost_matched") or {})
    n["matched_task_ids"] = cm.get("matched_task_ids") or []
    n["decisions"] = [d for d in decs if d["id"] == nid]
