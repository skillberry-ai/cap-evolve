"""Discover cap-evolve run dirs and project them via the engine's reducer."""
from __future__ import annotations

from pathlib import Path

from . import _bootstrap  # noqa: F401
from cap_evolve import RunDir, dashboard


class RunNotFound(Exception):
    pass


def resolve_run(base_dir: Path, run_id: str) -> Path:
    """Resolve ``run_id`` to a run dir that is a direct ``run_*`` child of ``base_dir``.

    Guards every filesystem-indexing route against path traversal: a ``run_id`` like
    ``..`` or ``../x`` resolves outside the base and is rejected, as is any name not
    prefixed ``run_`` or lacking ``events.jsonl``. Raises ``RunNotFound`` otherwise.
    """
    base = Path(base_dir).resolve()
    p = (base / run_id).resolve()
    if p.parent != base or not p.name.startswith("run_") or not (p / "events.jsonl").exists():
        raise RunNotFound(run_id)
    return p


def discover(base_dir: Path) -> list[Path]:
    base = Path(base_dir)
    if not base.is_dir():
        return []
    return [
        p for p in base.iterdir()
        if p.is_dir() and p.name.startswith("run_") and (p / "events.jsonl").exists()
    ]


def _reduce(path: Path) -> dict:
    rd = RunDir.open(path)
    return dashboard.reduce_run(rd)


def _status(summary: dict) -> str:
    # A run is "done" once finalize sealed the test; "failed" if there were no
    # accepted/seed nodes and no candidates; otherwise "live".
    if summary.get("test_reward") is not None or summary.get("test_sealed"):
        return "done"
    counts = summary.get("counts") or {}
    if counts.get("total", 0) == 0:
        return "failed"
    return "live"


def list_runs(base_dir: Path, limit: int | None = None, offset: int = 0) -> list[dict]:
    """Newest-first run rows, optionally a window of them.

    ``limit``/``offset`` page the list. The slice happens on the *discovered dirs*
    (ordered by dir mtime, which needs only a stat) BEFORE any reduction, so asking
    for one page costs one reduction per row on the page — not one per run in the
    dir. A run whose reduction raises (half-written) is skipped, so a page can come
    back shorter than ``limit`` — a SHORT PAGE IS NOT THE END OF THE LIST; page until
    you get an empty one.
    """
    # Name tiebreaks the mtime sort: runs created in the same tick would otherwise fall
    # back to iterdir() order, and pagination needs a total order to tile correctly.
    paths = sorted(discover(base_dir), key=lambda p: (-p.stat().st_mtime, p.name))
    if offset:
        paths = paths[offset:]
    if limit is not None:
        paths = paths[:limit]
    rows = []
    for path in paths:
        try:
            reduced = _reduce(path)
        except Exception:  # a half-written run must not break the hub
            continue
        s = reduced["summary"]
        counts = s.get("counts") or {}
        rows.append({
            "run_id": path.name,
            "path": str(path),
            "algorithm": s.get("algorithm"),
            "status": _status(s),
            "best_val": s.get("best_val"),
            "baseline_val": s.get("baseline_val"),
            "delta_pct": s.get("delta_pct"),
            "iterations": counts.get("accepted", 0) + counts.get("rejected", 0),
            "total_usd": (s.get("cost") or {}).get("total_usd"),
            "mtime": path.stat().st_mtime,
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def load_run(base_dir: Path, run_id: str) -> dict:
    path = resolve_run(base_dir, run_id)
    reduced = _reduce(path)
    return {"run_id": run_id, "path": str(path), **reduced}
