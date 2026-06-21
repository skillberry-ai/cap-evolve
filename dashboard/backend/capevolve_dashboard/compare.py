"""Project multiple runs into a side-by-side comparison payload."""
from __future__ import annotations

from pathlib import Path

from . import runs


def _series(graph: dict) -> list[dict]:
    nodes = sorted(graph.get("nodes", []), key=lambda n: n.get("iteration") or 0)
    out, best = [], None
    for n in nodes:
        v = n.get("val")
        if v is None:
            continue
        best = v if best is None else max(best, v)
        out.append({"iteration": n.get("iteration") or 0, "best_so_far": best})
    return out


def compare_runs(base_dir: Path, run_ids: list[str]) -> dict:
    rows, all_tasks = [], []
    for rid in run_ids:
        try:
            data = runs.load_run(base_dir, rid)
        except runs.RunNotFound:
            continue
        s, g = data["summary"], data["graph"]
        counts = s.get("counts") or {}
        rows.append({
            "run_id": rid, "algorithm": s.get("algorithm"),
            "baseline_val": s.get("baseline_val"), "best_val": s.get("best_val"),
            "delta_pct": s.get("delta_pct"), "test_reward": s.get("test_reward"),
            "total_usd": (s.get("cost") or {}).get("total_usd"), "tokens": s.get("tokens"),
            "iterations": counts.get("accepted", 0) + counts.get("rejected", 0),
            "series": _series(g),
        })
        for t in s.get("tasks", []):
            if t not in all_tasks:
                all_tasks.append(t)
    return {"runs": rows, "tasks": all_tasks}
