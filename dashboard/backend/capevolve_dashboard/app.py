"""FastAPI app factory serving cap-evolve run data (read-only)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import compare, runs, trajectories
from . import memory as _memory
from . import stream as _stream
from . import files as _files
from . import gitlog as _gitlog


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

    def _resolve_or_404(run_id: str) -> Path:
        try:
            return runs.resolve_run(base, run_id)
        except runs.RunNotFound:
            raise HTTPException(status_code=404, detail="run not found")

    @app.get("/api/runs/{run_id}/rollouts")
    def get_rollouts(run_id: str, split: str | None = Query(default=None)):
        return trajectories.list_rollouts(_resolve_or_404(run_id), split)

    @app.get("/api/runs/{run_id}/rollout/{file_name}")
    def get_rollout(run_id: str, file_name: str):
        path = _resolve_or_404(run_id)
        try:
            return trajectories.read_rollout(path, file_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="rollout not found")

    @app.get("/api/runs/{run_id}/diff/{candidate}")
    def get_diff(run_id: str, candidate: str):
        return trajectories.diff_candidate(_resolve_or_404(run_id), candidate)

    @app.get("/api/runs/{run_id}/memory")
    def get_memory(run_id: str):
        return _memory.read_memory(_resolve_or_404(run_id))

    @app.get("/api/runs/{run_id}/candidate/{candidate}/files")
    def get_candidate_files(run_id: str, candidate: str):
        return _memory.list_candidate_files(_resolve_or_404(run_id), candidate)

    @app.get("/api/runs/{run_id}/tree")
    def get_tree(run_id: str, path: str = Query(default="")):
        try:
            return _files.tree(_resolve_or_404(run_id), path)
        except PermissionError:
            raise HTTPException(status_code=400, detail="path escapes run dir")

    @app.get("/api/runs/{run_id}/file")
    def get_file(run_id: str, path: str = Query(...)):
        try:
            return _files.read_file(_resolve_or_404(run_id), path)
        except PermissionError:
            raise HTTPException(status_code=400, detail="path escapes run dir")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file not found")

    @app.get("/api/runs/{run_id}/git/log")
    def get_git_log(run_id: str):
        return _gitlog.log(_resolve_or_404(run_id))

    @app.get("/api/runs/{run_id}/git/diff")
    def get_git_diff(run_id: str, frm: str = Query(..., alias="from"), to: str = Query(...)):
        return _gitlog.diff(_resolve_or_404(run_id), frm, to)

    @app.get("/api/compare")
    def get_compare(ids: str = Query(...)):
        run_ids = [x for x in ids.split(",") if x]
        return compare.compare_runs(base, run_ids)

    @app.get("/api/runs/{run_id}/stream")
    async def run_stream(run_id: str):
        events_path = _resolve_or_404(run_id) / "events.jsonl"

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
