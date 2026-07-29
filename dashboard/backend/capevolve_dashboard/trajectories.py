"""Read per-task rollouts and per-candidate diffs from a run dir."""
from __future__ import annotations

import json
import re
from pathlib import Path

from cap_evolve import RunDir, dashboard

_ROLLOUT_RE = re.compile(r"^(?P<task>.+)__(?P<cand>cand_\d+|seed)__t(?P<trial>\d+)\.json$")


def list_rollouts(run_path: Path, split: str | None = None,
                  limit: int | None = None, offset: int = 0) -> list[dict]:
    """Rollout rows for a run, optionally a window of them.

    ``limit``/``offset`` page the result. The window is applied to the sorted FILE
    NAMES before any file is opened, so a page costs one JSON parse per row on the
    page rather than one per rollout in the split (a long run has thousands). Order
    is stable: splits sorted by name, then file name within a split. A file that fails
    to parse is skipped, so a page can be shorter than ``limit`` — a SHORT PAGE IS NOT
    THE END OF THE LIST; page until you get an empty one.
    """
    root = Path(run_path) / "rollouts"
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    splits = [split] if split else sorted(p.name for p in root.iterdir() if p.is_dir())
    # Name-matching is a cheap regex on the filename; do it first so paging indexes
    # over the rows the caller will actually see, then window, then open the files.
    matched: list[tuple[str, Path, re.Match]] = []
    for sp in splits:
        sp_dir = root / sp
        if not sp_dir.is_dir():
            continue
        for f in sorted(sp_dir.glob("*.json")):
            m = _ROLLOUT_RE.match(f.name)
            if m:
                matched.append((sp, f, m))
    if offset:
        matched = matched[offset:]
    if limit is not None:
        matched = matched[:limit]
    for sp, f, m in matched:
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
