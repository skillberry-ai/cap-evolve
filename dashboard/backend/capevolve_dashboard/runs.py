"""Discover cap-evolve run dirs and project them via the engine's reducer."""
from __future__ import annotations

from pathlib import Path

from . import _bootstrap  # noqa: F401
from cap_evolve import RunDir, dashboard, eventstream


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


def liveness(path: Path) -> dict:
    """Fresh stall/crash facts for a run dir — deliberately NOT part of ``_reduce``.

    ``reduce_run`` is cached on the run's on-disk stamp (#119), and "how long has this
    run been silent" is the one fact that changes precisely *while nothing on disk
    changes*: a cached answer would be permanently 0s. So it is computed here, per
    request, from the same ``cap_evolve.eventstream`` helpers the terminal uses — one
    ``stat`` plus one read of ``events.jsonl``, no reduction.
    """
    try:
        facts = eventstream.liveness_facts(path)
        return {"status": eventstream.classify(facts),
                "detail": eventstream.describe_status(facts),
                "silence_seconds": facts["silence"],
                "stall_threshold_seconds": facts["threshold"],
                "slowest_gap_seconds": facts["slowest_gap"],
                "process_alive": facts["alive"]}
    except Exception:  # noqa: BLE001 — a hub row must never 500 over a liveness probe
        return {"status": "live", "detail": None, "silence_seconds": None,
                "stall_threshold_seconds": None, "slowest_gap_seconds": None,
                "process_alive": None}


def _status(summary: dict, live: dict | None = None) -> str:
    """``done`` / ``failed`` / ``crashed`` / ``stalled`` / ``live``.

    ``done`` and ``failed`` are decided from the reduced summary and stay FIRST: a
    finished run must degrade to a clean "done" no matter that its process is long
    gone and its log has been silent for a week (#118). Only a run that is neither
    finished nor empty is subject to the liveness verdict, which is where ``stalled``
    and ``crashed`` come from — previously such a run read ``live`` forever.
    """
    verdict = (live or {}).get("status")
    # `test_sealed`/`test_reward` come from splits.json/final.json; the `finalize` EVENT
    # is the same fact seen in the log, and it is what the terminal reads. Accept either,
    # or the two surfaces disagree about a run whose artifacts lag its log.
    if summary.get("test_reward") is not None or summary.get("test_sealed") \
            or verdict == "done":
        return "done"
    counts = summary.get("counts") or {}
    if counts.get("total", 0) == 0:
        return "failed"
    return verdict if verdict in ("stalled", "crashed") else "live"


def list_runs(base_dir: Path) -> list[dict]:
    rows = []
    for path in discover(base_dir):
        try:
            reduced = _reduce(path)
        except Exception:  # a half-written run must not break the hub
            continue
        s = reduced["summary"]
        counts = s.get("counts") or {}
        live = liveness(path)
        rows.append({
            "run_id": path.name,
            "path": str(path),
            "algorithm": s.get("algorithm"),
            "status": _status(s, live),
            "liveness": live,
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
    live = liveness(path)
    # Same key, same computation, same source of truth as the hub row and as
    # `cap-evolve tail` — so the two surfaces cannot report different verdicts.
    reduced["summary"]["liveness"] = live
    reduced["summary"]["status"] = _status(reduced["summary"], live)
    return {"run_id": run_id, "path": str(path), **reduced}
