"""Read per-task rollouts and per-candidate diffs from a run dir."""
from __future__ import annotations

import json
import re
from pathlib import Path

from cap_evolve import RunDir, dashboard

_ROLLOUT_RE = re.compile(r"^(?P<task>.+)__(?P<cand>cand_\d+|seed)__t(?P<trial>\d+)\.json$")


def list_rollouts(run_path: Path, split: str | None = None) -> list[dict]:
    root = Path(run_path) / "rollouts"
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    splits = [split] if split else [p.name for p in root.iterdir() if p.is_dir()]
    for sp in splits:
        sp_dir = root / sp
        if not sp_dir.is_dir():
            continue
        for f in sorted(sp_dir.glob("*.json")):
            m = _ROLLOUT_RE.match(f.name)
            if not m:
                continue
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            score = data.get("score") or {}
            rows.append({
                "task_id": m["task"], "candidate": m["cand"],
                "trial": int(m["trial"]), "split": sp,
                "reward": score.get("reward"), "feedback": score.get("feedback", ""),
                "file": f.name,
            })
    return rows


def read_rollout(run_path: Path, file_name: str) -> dict:
    safe = Path(file_name).name  # strip any path components from the basename
    # sorted() makes the result deterministic if the same basename exists under
    # multiple splits; run_path is already a validated run dir (see resolve_run).
    for f in sorted((Path(run_path) / "rollouts").rglob(safe)):
        return dashboard.redact(json.loads(f.read_text()))
    raise FileNotFoundError(file_name)


def diff_candidate(run_path: Path, candidate_id: str) -> dict:
    """Per-candidate diff vs parent.

    The engine's ``build_diffs`` returns ``{node_id: [{"file", "rows":[{"t","l"}]}]}``
    (a list of per-file diffs; ``t`` is ``add|del|ctx|hunk``). Empty when candidate
    dirs weren't snapshotted. The parent id lives on the graph node, so we read it
    there and project a stable shape with per-file add/remove counts for the UI.
    """
    rd = RunDir.open(Path(run_path))
    reduced = dashboard.reduce_run(rd)
    graph = reduced["graph"]
    node = next((n for n in graph.get("nodes", []) if n.get("id") == candidate_id), None)
    parent = node.get("parent") if node else None
    diffs = dashboard.build_diffs(rd, graph) or {}
    files = []
    for entry in diffs.get(candidate_id, []):
        rows = entry.get("rows", [])
        files.append({
            "path": entry.get("file"),
            "added": sum(1 for r in rows if r.get("t") == "add"),
            "removed": sum(1 for r in rows if r.get("t") == "del"),
            "rows": rows,
        })
    return {"candidate": candidate_id, "parent": parent, "files": files}
