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


def list_runs(base_dir: Path) -> list[dict]:
    rows = []
    for path in discover(base_dir):
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
            # Status comes straight from the reducer, which derives it from the event
            # log's own evidence (finalize / budget / silence). The old local helper
            # called every unfinalized run "live", including ones that died weeks ago.
            "status": s.get("status"),
            "status_reason": s.get("status_reason"),
            "best_val": s.get("best_val"),
            "baseline_val": s.get("baseline_val"),
            "delta_pct": s.get("delta_pct"),
            # Absolute Δ too: the relative % is undefined off a zero baseline, which is
            # the normal case for a run whose seed scores 0.
            "delta_abs": s.get("delta_abs"),
            "test_reward": s.get("test_reward"),
            "iterations": (counts.get("accepted", 0) + counts.get("rejected", 0)
                           + counts.get("indecisive", 0) + counts.get("failed", 0)),
            "total_usd": (s.get("cost") or {}).get("total_usd"),
            # $0 after real calls is UNMETERED, not free. The hub must not print
            # "$0.000" for a run whose runner reports no cost.
            "cost_metered": (s.get("cost") or {}).get("metered", True),
            "last_event_t": s.get("last_event_t"),
            "mtime": path.stat().st_mtime,
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def load_run(base_dir: Path, run_id: str) -> dict:
    path = resolve_run(base_dir, run_id)
    reduced = _reduce(path)
    return {"run_id": run_id, "path": str(path), **reduced}
