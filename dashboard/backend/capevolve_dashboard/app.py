"""FastAPI app factory serving cap-evolve run data (read-only)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import runs, trajectories
from . import stream as _stream


def create_app(base_dir: Path, static_dir: Path | None = None) -> FastAPI:
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

    @app.get("/api/runs/{run_id}/rollouts")
    def get_rollouts(run_id: str, split: str | None = Query(default=None)):
        path = base / run_id
        if not (path / "events.jsonl").exists():
            raise HTTPException(status_code=404, detail="run not found")
        return trajectories.list_rollouts(path, split)

    @app.get("/api/runs/{run_id}/rollout/{file_name}")
    def get_rollout(run_id: str, file_name: str):
        path = base / run_id
        try:
            return trajectories.read_rollout(path, file_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="rollout not found")

    @app.get("/api/runs/{run_id}/diff/{candidate}")
    def get_diff(run_id: str, candidate: str):
        path = base / run_id
        if not (path / "events.jsonl").exists():
            raise HTTPException(status_code=404, detail="run not found")
        return trajectories.diff_candidate(path, candidate)

    @app.get("/api/compare")
    def get_compare(ids: str = Query(...)):
        from . import compare
        run_ids = [x for x in ids.split(",") if x]
        return compare.compare_runs(base, run_ids)

    @app.get("/api/runs/{run_id}/stream")
    async def run_stream(run_id: str):
        path = base / run_id
        events_path = path / "events.jsonl"
        if not events_path.exists():
            raise HTTPException(status_code=404, detail="run not found")

        async def gen():
            # Initial snapshot of the full reduced run.
            try:
                yield _stream.sse_format("snapshot", runs.load_run(base, run_id))
            except runs.RunNotFound:
                return
            offset = events_path.stat().st_size
            idle = 0
            while True:
                new, offset = _stream.read_new_events(events_path, offset)
                for ev in new:
                    yield _stream.sse_format("event", ev)
                    if ev.get("kind") == "finalize":
                        yield _stream.sse_format("done", {"run_id": run_id})
                        return
                idle = idle + 1 if not new else 0
                if idle > 600:  # ~5 min of silence -> stop holding the connection
                    yield _stream.sse_format("idle", {"run_id": run_id})
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(gen(), media_type="text/event-stream")

    if static_dir is not None and Path(static_dir).is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
