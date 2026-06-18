"""FastAPI app factory serving cap-evolve run data (read-only)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from . import runs


def create_app(base_dir: Path) -> FastAPI:
    base = Path(base_dir)
    app = FastAPI(title="cap-evolve dashboard", version="0.1.0")
    app.state.base_dir = base

    @app.get("/api/health")
    def health():
        return {"ok": True, "base_dir": str(base)}

    @app.get("/api/runs")
    def get_runs():
        return runs.list_runs(base)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return runs.load_run(base, run_id)
        except runs.RunNotFound:
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")

    return app
