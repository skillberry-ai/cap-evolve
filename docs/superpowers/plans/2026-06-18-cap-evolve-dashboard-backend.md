# cap-evolve Dashboard — Backend (Plan 1 of 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI data backend that serves cap-evolve run-dir data (hub list, single-run deep-dive, trajectories, diffs, compare) plus a live SSE stream, reusing the engine's `reduce_run()` so the data contract stays single-sourced.

**Architecture:** A new **optional** package `agent-capo/dashboard/backend/` (its own deps; the stdlib-only core is untouched). It imports `cap_evolve.dashboard.reduce_run` to fold each run dir into `{graph, summary}`, exposes read-only JSON endpoints over discovered run dirs, tails the append-only `events.jsonl` for live updates via Server-Sent Events, and (later tasks) serves the built React assets and provides an idempotent launch helper.

**Tech Stack:** Python ≥3.10, FastAPI, Uvicorn, Starlette `StreamingResponse` for SSE (no extra SSE dep), pytest + Starlette `TestClient` (httpx). Reuses `cap-evolve-core` (`cap_evolve` package).

## Global Constraints

- Python floor: **>=3.10** (matches `core/pyproject.toml`).
- **Do NOT add any dependency to `core/`** — it is stdlib-only by design (`core/pyproject.toml` `dependencies = []`). All new deps live in `dashboard/backend/pyproject.toml`.
- **Single-sourced data contract:** all run data is derived via `cap_evolve.dashboard.reduce_run(run_dir)` → `{"graph": {...}, "summary": {...}}`. Do not re-implement reduction.
- **Read-only:** the backend never writes into run dirs.
- `reduce_run` already **redacts secrets**; do not undo or bypass `redact()`.
- Run dirs are discovered under a base dir (default `.capevolve/`) as directories named `run_*` that contain `events.jsonl`.
- Test fixtures available in-repo: `.demo/.agentcapo/run_demo/`, `examples/tau2_airline/run_full/hillclimb_run/`, `examples/tau2_airline/run_full/gepa_run/`. Synthetic run dirs are built with `cap_evolve.RunDir.create(...)` + writing `events.jsonl` (see existing `core/tests/test_dashboard.py` `_mk_run` helper).

**Graph schema** (`reduced["graph"]`): `{"nodes": [{"id","parent","children":[...],"status": seed|accepted|rejected|failed,"val","stderr","per_task":{task_id:reward},"feedback":{task_id:str},"cost_usd","tokens","seconds","optimizer_seconds","runner_seconds","iteration","reason","epoch"?,"merge_of"?,"best_so_far"}], "root": "seed", "best_id": "..."}`

**Summary schema** (`reduced["summary"]`): `{"run_id","baseline_val","best_val","delta_pct","test_reward","test_sealed","test_pass_k","counts":{accepted,rejected,failed,seed,total},"frontier":int,"tasks":[...],"wall_clock_seconds","optimizer_seconds","runner_seconds","cost":{optimizer_usd,runner_usd,total_usd},"tokens":int,"gate_warnings":[...],"diagnoses":[...],"git_log":[...]}`

---

## File Structure

- Create `dashboard/backend/pyproject.toml` — package metadata + deps (fastapi, uvicorn, httpx; dev: pytest).
- Create `dashboard/backend/capevolve_dashboard/__init__.py` — package marker + version.
- Create `dashboard/backend/capevolve_dashboard/_bootstrap.py` — ensures `cap_evolve` importable (mirrors core's `_bootstrap.py` pattern).
- Create `dashboard/backend/capevolve_dashboard/runs.py` — run-dir discovery + reduction projection (`list_runs`, `load_run`, `RunNotFound`).
- Create `dashboard/backend/capevolve_dashboard/trajectories.py` — rollout + git-diff readers (`list_rollouts`, `read_rollout`, `diff_candidate`).
- Create `dashboard/backend/capevolve_dashboard/compare.py` — multi-run comparison projection (`compare_runs`).
- Create `dashboard/backend/capevolve_dashboard/stream.py` — `tail_events(path)` generator + `sse_format(event)`.
- Create `dashboard/backend/capevolve_dashboard/app.py` — FastAPI app factory `create_app(base_dir)` + routes + static mount.
- Create `dashboard/backend/capevolve_dashboard/server.py` — idempotent launch helper (`is_up`, `launch`, `ensure_up`).
- Create `dashboard/backend/tests/conftest.py` — path bootstrap + fixtures (`tmp_base`, `make_run`).
- Create `dashboard/backend/tests/test_runs.py`, `test_app.py`, `test_trajectories.py`, `test_compare.py`, `test_stream.py`, `test_server.py`.

---

### Task 1: Package scaffold + run discovery

**Files:**
- Create: `dashboard/backend/pyproject.toml`
- Create: `dashboard/backend/capevolve_dashboard/__init__.py`
- Create: `dashboard/backend/capevolve_dashboard/_bootstrap.py`
- Create: `dashboard/backend/capevolve_dashboard/runs.py`
- Create: `dashboard/backend/tests/conftest.py`
- Test: `dashboard/backend/tests/test_runs.py`

**Interfaces:**
- Produces:
  - `runs.list_runs(base_dir: Path) -> list[dict]` — one light summary per run, sorted newest-first. Each dict: `{"run_id": str, "path": str, "algorithm": str|None, "status": "live"|"done"|"failed", "best_val": float|None, "baseline_val": float|None, "delta_pct": float|None, "iterations": int, "total_usd": float|None, "mtime": float}`.
  - `runs.load_run(base_dir: Path, run_id: str) -> dict` — full `{"graph","summary"}` from `reduce_run`, plus `"run_id"` and `"path"`. Raises `runs.RunNotFound` if missing.
  - `runs.RunNotFound(Exception)`.
  - `runs.discover(base_dir: Path) -> list[Path]` — run dirs (`run_*` containing `events.jsonl`).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "capevolve-dashboard"
version = "0.1.0"
description = "Live FastAPI dashboard backend for cap-evolve runs."
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["fastapi>=0.110", "uvicorn>=0.27", "cap-evolve-core"]

[project.optional-dependencies]
dev = ["pytest>=7", "httpx>=0.27"]

[project.scripts]
cap-evolve-dashboard = "capevolve_dashboard.server:main"

[tool.setuptools]
packages = ["capevolve_dashboard"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `_bootstrap.py`** (make `cap_evolve` importable without install)

```python
"""Ensure the stdlib-only ``cap_evolve`` core is importable.

Prefer an installed ``cap-evolve-core``; fall back to the in-repo ``core/`` dir
so tests and dev runs work from a checkout (mirrors core's own _bootstrap.py).
"""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_core_on_path() -> None:
    try:
        import cap_evolve  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    # dashboard/backend/capevolve_dashboard/_bootstrap.py -> repo root is parents[3]
    core = Path(__file__).resolve().parents[3] / "core"
    if core.is_dir():
        sys.path.insert(0, str(core))


ensure_core_on_path()
```

- [ ] **Step 3: Write `__init__.py`**

```python
from . import _bootstrap  # noqa: F401  (side effect: cap_evolve on path)

__version__ = "0.1.0"
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import capevolve_dashboard  # noqa: E402,F401  (bootstraps cap_evolve onto path)


@pytest.fixture
def tmp_base(tmp_path):
    """An empty base dir that will hold run_* dirs."""
    return tmp_path


@pytest.fixture
def make_run(tmp_base):
    """Create a synthetic run dir under tmp_base; return its RunDir."""
    from cap_evolve import Budget, RunDir

    def _make(run_id="run_t", *, events, baseline=None, final=None):
        ts = run_id[len("run_"):] if run_id.startswith("run_") else run_id
        rd = RunDir.create(tmp_base, ts=ts, budget=Budget())
        rd.events_path.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
        if baseline is not None:
            (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        if final is not None:
            (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
        return rd

    return _make


# Shared minimal event stream: baseline + one accepted + one rejected candidate.
BASE_EVENTS = [
    {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
     "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 0.0},
    {"kind": "baseline", "val": 0.25, "stderr": 0.0},
    {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
     "val": 0.75, "parent": "seed", "parent_val": 0.25,
     "optimizer_seconds": 1.2, "runner_seconds": 0.5, "cost_usd": 0.01, "tokens": 500},
    {"kind": "step", "candidate": "cand_0002", "accept": False, "reason": "down",
     "val": 0.6, "parent": "cand_0001", "parent_val": 0.75,
     "optimizer_seconds": 1.0, "runner_seconds": 0.4, "cost_usd": 0.008, "tokens": 400},
]
```

- [ ] **Step 5: Write the failing test** in `tests/test_runs.py`

```python
from pathlib import Path

from conftest import BASE_EVENTS


def test_discover_finds_run_dirs(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS)
    make_run("run_b", events=BASE_EVENTS)
    (tmp_base / "not_a_run").mkdir()
    found = runs.discover(tmp_base)
    names = sorted(p.name for p in found)
    assert names == ["run_a", "run_b"]


def test_list_runs_projects_light_summary(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    rows = runs.list_runs(tmp_base)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run_a"
    assert row["baseline_val"] == 0.25
    assert row["best_val"] == 0.75
    assert row["iterations"] == 2
    assert row["status"] in {"live", "done", "failed"}


def test_load_run_returns_graph_and_summary(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    data = runs.load_run(tmp_base, "run_a")
    assert data["run_id"] == "run_a"
    assert "graph" in data and "summary" in data
    assert data["graph"]["best_id"] == "cand_0001"


def test_load_run_missing_raises(tmp_base):
    import pytest
    from capevolve_dashboard import runs
    with pytest.raises(runs.RunNotFound):
        runs.load_run(tmp_base, "run_nope")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd dashboard/backend && python -m pytest tests/test_runs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.runs'`.

- [ ] **Step 7: Write `runs.py`**

```python
"""Discover cap-evolve run dirs and project them via the engine's reducer."""
from __future__ import annotations

from pathlib import Path

from . import _bootstrap  # noqa: F401
from cap_evolve import RunDir, dashboard


class RunNotFound(Exception):
    pass


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


def _status(summary: dict, path: Path) -> str:
    # A run is "done" once finalize sealed the test; "failed" if there were no
    # accepted/seed nodes and no candidates; otherwise "live".
    if summary.get("test_reward") is not None or summary.get("test_sealed"):
        return "done"
    counts = summary.get("counts") or {}
    if counts.get("total", 0) == 0:
        return "failed"
    return "live"


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
            "status": _status(s, path),
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
    path = Path(base_dir) / run_id
    if not (path.is_dir() and (path / "events.jsonl").exists()):
        raise RunNotFound(run_id)
    reduced = _reduce(path)
    return {"run_id": run_id, "path": str(path), **reduced}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd dashboard/backend && python -m pytest tests/test_runs.py -v`
Expected: PASS (4 passed).

Note: if `test_list_runs_projects_light_summary` shows `algorithm` is `None`, that is acceptable — the field is best-effort; the assertions above do not require it.

- [ ] **Step 9: Commit**

```bash
git add dashboard/backend/pyproject.toml dashboard/backend/capevolve_dashboard/ dashboard/backend/tests/
git commit -m "feat(dashboard): backend run discovery + reducer projection"
```

---

### Task 2: FastAPI app — `/api/runs` and `/api/runs/{id}`

**Files:**
- Create: `dashboard/backend/capevolve_dashboard/app.py`
- Test: `dashboard/backend/tests/test_app.py`

**Interfaces:**
- Consumes: `runs.list_runs`, `runs.load_run`, `runs.RunNotFound`.
- Produces: `app.create_app(base_dir: Path) -> fastapi.FastAPI` with routes `GET /api/health`, `GET /api/runs`, `GET /api/runs/{run_id}`.

- [ ] **Step 1: Write the failing test** in `tests/test_app.py`

```python
from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def test_health(tmp_base):
    r = _client(tmp_base).get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_list_runs_endpoint(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = _client(tmp_base).get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["run_id"] == "run_a"


def test_get_run_endpoint(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = _client(tmp_base).get("/api/runs/run_a")
    assert r.status_code == 200
    assert r.json()["graph"]["best_id"] == "cand_0001"


def test_get_missing_run_404(tmp_base):
    r = _client(tmp_base).get("/api/runs/run_nope")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.app'`.

- [ ] **Step 3: Write `app.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard/backend && python -m pytest tests/test_app.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/app.py dashboard/backend/tests/test_app.py
git commit -m "feat(dashboard): FastAPI /api/runs and /api/runs/{id}"
```

---

### Task 3: Trajectories — rollouts + diff endpoints

**Files:**
- Create: `dashboard/backend/capevolve_dashboard/trajectories.py`
- Modify: `dashboard/backend/capevolve_dashboard/app.py` (add 3 routes)
- Test: `dashboard/backend/tests/test_trajectories.py`

**Interfaces:**
- Consumes: `runs.RunNotFound`; `cap_evolve.dashboard.build_diffs`, `redact`.
- Produces:
  - `trajectories.list_rollouts(run_path: Path, split: str|None=None) -> list[dict]` — `[{"task_id","candidate","trial","split","reward","feedback","file"}]`.
  - `trajectories.read_rollout(run_path: Path, file_name: str) -> dict` — the redacted rollout JSON (`{"input","rollout","score"}`); raises `FileNotFoundError`.
  - `trajectories.diff_candidate(run_path: Path, candidate_id: str) -> dict` — `{"candidate","parent","files":[{"path","added","removed","patch"}]}` (empty `files` if no git/parent).
  - Routes: `GET /api/runs/{id}/rollouts?split=`, `GET /api/runs/{id}/rollout/{file}`, `GET /api/runs/{id}/diff/{candidate}`.

- [ ] **Step 1: Write the failing test** in `tests/test_trajectories.py`

```python
import json

from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def _write_rollout(rd, split, task, cand, trial, reward, feedback):
    d = rd.root / "rollouts" / split
    d.mkdir(parents=True, exist_ok=True)
    name = f"{task}__{cand}__t{trial}.json"
    (d / name).write_text(json.dumps({
        "input": f"in-{task}",
        "rollout": {"task_id": task, "output": "out", "trace": "...",
                    "tool_calls": [{"name": "calc"}], "cost_usd": 0.0,
                    "tokens": 0, "error": None, "metadata": {}},
        "score": {"task_id": task, "reward": reward, "feedback": feedback,
                  "n": 1, "stderr": 0.0, "trial_rewards": [reward], "raw": {}},
    }), encoding="utf-8")
    return name


def test_list_rollouts(tmp_base, make_run):
    from capevolve_dashboard import trajectories
    rd = make_run("run_a", events=BASE_EVENTS)
    _write_rollout(rd, "val", "t1", "cand_0001", 0, 1.0, "correct")
    _write_rollout(rd, "val", "t2", "cand_0001", 0, 0.0, "wrong")
    rows = trajectories.list_rollouts(rd.root)
    assert {r["task_id"] for r in rows} == {"t1", "t2"}
    assert all(r["candidate"] == "cand_0001" for r in rows)


def test_rollouts_endpoint(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    _write_rollout(rd, "val", "t1", "cand_0001", 0, 1.0, "correct")
    r = _client(tmp_base).get("/api/runs/run_a/rollouts?split=val")
    assert r.status_code == 200
    assert r.json()[0]["task_id"] == "t1"


def test_diff_endpoint_no_git_is_empty(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS)
    r = _client(tmp_base).get("/api/runs/run_a/diff/cand_0001")
    assert r.status_code == 200
    assert r.json()["files"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_trajectories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.trajectories'`.

- [ ] **Step 3: Write `trajectories.py`**

```python
"""Read per-task rollouts and per-candidate git diffs from a run dir."""
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
    safe = Path(file_name).name  # prevent path traversal
    for f in (Path(run_path) / "rollouts").rglob(safe):
        return dashboard.redact(json.loads(f.read_text()))
    raise FileNotFoundError(file_name)


def diff_candidate(run_path: Path, candidate_id: str) -> dict:
    rd = RunDir.open(Path(run_path))
    reduced = dashboard.reduce_run(rd)
    diffs = dashboard.build_diffs(rd, reduced["graph"]) or {}
    entry = diffs.get(candidate_id) or {}
    return {
        "candidate": candidate_id,
        "parent": entry.get("parent"),
        "files": entry.get("files", []),
    }
```

Note: `build_diffs` returns a mapping keyed by candidate id with each value containing `parent` and a `files` list (`{"path","added","removed","patch"}`) — confirm the exact key names against `core/cap_evolve/dashboard.py:build_diffs` (≈line 414) while implementing and adapt the projection above to match; keep the route's response shape stable.

- [ ] **Step 4: Add routes to `app.py`** (inside `create_app`, before `return app`)

```python
    from fastapi import Query
    from . import trajectories

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd dashboard/backend && python -m pytest tests/test_trajectories.py tests/test_app.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/trajectories.py dashboard/backend/capevolve_dashboard/app.py dashboard/backend/tests/test_trajectories.py
git commit -m "feat(dashboard): rollout + diff endpoints"
```

---

### Task 4: Compare endpoint

**Files:**
- Create: `dashboard/backend/capevolve_dashboard/compare.py`
- Modify: `dashboard/backend/capevolve_dashboard/app.py` (add route)
- Test: `dashboard/backend/tests/test_compare.py`

**Interfaces:**
- Consumes: `runs.load_run`, `runs.RunNotFound`.
- Produces:
  - `compare.compare_runs(base_dir: Path, run_ids: list[str]) -> dict` — `{"runs": [{"run_id","algorithm","baseline_val","best_val","delta_pct","test_reward","total_usd","tokens","iterations","series":[{"iteration":int,"best_so_far":float}]}], "tasks": [task_id,...]}`. Unknown ids are skipped.
  - Route: `GET /api/compare?ids=run_a,run_b`.

- [ ] **Step 1: Write the failing test** in `tests/test_compare.py`

```python
from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def test_compare_runs(tmp_base, make_run):
    from capevolve_dashboard import compare
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    make_run("run_b", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    out = compare.compare_runs(tmp_base, ["run_a", "run_b"])
    assert [r["run_id"] for r in out["runs"]] == ["run_a", "run_b"]
    assert out["runs"][0]["best_val"] == 0.75
    assert isinstance(out["runs"][0]["series"], list)


def test_compare_endpoint_skips_unknown(tmp_base, make_run):
    from capevolve_dashboard.app import create_app
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = TestClient(create_app(tmp_base)).get("/api/compare?ids=run_a,run_ghost")
    assert r.status_code == 200
    assert [x["run_id"] for x in r.json()["runs"]] == ["run_a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_compare.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.compare'`.

- [ ] **Step 3: Write `compare.py`**

```python
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
```

- [ ] **Step 4: Add route to `app.py`** (inside `create_app`, before `return app`)

```python
    @app.get("/api/compare")
    def get_compare(ids: str = Query(...)):
        from . import compare
        run_ids = [x for x in ids.split(",") if x]
        return compare.compare_runs(base, run_ids)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd dashboard/backend && python -m pytest tests/test_compare.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/compare.py dashboard/backend/capevolve_dashboard/app.py dashboard/backend/tests/test_compare.py
git commit -m "feat(dashboard): cross-run compare endpoint"
```

---

### Task 5: Live SSE stream

**Files:**
- Create: `dashboard/backend/capevolve_dashboard/stream.py`
- Modify: `dashboard/backend/capevolve_dashboard/app.py` (add SSE route)
- Test: `dashboard/backend/tests/test_stream.py`

**Interfaces:**
- Produces:
  - `stream.sse_format(event: str, data: dict) -> str` — `"event: {event}\ndata: {json}\n\n"`.
  - `stream.read_new_events(path: Path, offset: int) -> tuple[list[dict], int]` — parse `events.jsonl` from byte `offset`, returning new events + the new byte offset (partial trailing line is not consumed).
  - Route: `GET /api/runs/{id}/stream` — `text/event-stream`; emits a `snapshot` event (current reduced run) then `event` events as new lines append; closes when the run is `done` (finalize seen) or client disconnects.

- [ ] **Step 1: Write the failing test** in `tests/test_stream.py`

```python
import json


def test_sse_format():
    from capevolve_dashboard import stream
    out = stream.sse_format("event", {"kind": "step"})
    assert out == 'event: event\ndata: {"kind": "step"}\n\n'


def test_read_new_events_incremental(tmp_path):
    from capevolve_dashboard import stream
    p = tmp_path / "events.jsonl"
    p.write_text(json.dumps({"kind": "baseline", "val": 0.25}) + "\n", encoding="utf-8")
    events, off = stream.read_new_events(p, 0)
    assert events == [{"kind": "baseline", "val": 0.25}]
    assert off == p.stat().st_size

    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "step", "candidate": "cand_0001"}) + "\n")
    events2, off2 = stream.read_new_events(p, off)
    assert events2 == [{"kind": "step", "candidate": "cand_0001"}]
    assert off2 == p.stat().st_size


def test_read_new_events_ignores_partial_trailing_line(tmp_path):
    from capevolve_dashboard import stream
    p = tmp_path / "events.jsonl"
    p.write_text('{"kind": "baseline"}\n{"kind": "ste', encoding="utf-8")  # partial
    events, off = stream.read_new_events(p, 0)
    assert events == [{"kind": "baseline"}]
    assert off == len('{"kind": "baseline"}\n')  # partial line not consumed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_stream.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.stream'`.

- [ ] **Step 3: Write `stream.py`**

```python
"""Server-Sent-Events helpers: format frames and tail events.jsonl by byte offset."""
from __future__ import annotations

import json
from pathlib import Path


def sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def read_new_events(path: Path, offset: int) -> tuple[list[dict], int]:
    """Return (new events, new byte offset). A partial trailing line (no newline)
    is left unconsumed so the next read picks it up once complete."""
    p = Path(path)
    if not p.exists():
        return [], offset
    raw = p.read_bytes()
    if offset >= len(raw):
        return [], offset
    chunk = raw[offset:]
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return [], offset  # only a partial line so far
    complete = chunk[: last_nl + 1]
    events = []
    for line in complete.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, offset + last_nl + 1
```

- [ ] **Step 4: Add the SSE route to `app.py`** (inside `create_app`, before `return app`)

```python
    import asyncio
    from fastapi.responses import StreamingResponse
    from . import stream as _stream

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd dashboard/backend && python -m pytest tests/test_stream.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/stream.py dashboard/backend/capevolve_dashboard/app.py dashboard/backend/tests/test_stream.py
git commit -m "feat(dashboard): live SSE stream tailing events.jsonl"
```

---

### Task 6: Static asset serving (built frontend)

**Files:**
- Modify: `dashboard/backend/capevolve_dashboard/app.py` (mount static dir if present)
- Test: `dashboard/backend/tests/test_app.py` (add one test)

**Interfaces:**
- Consumes: optional `static_dir: Path` param on `create_app`.
- Produces: `create_app(base_dir, static_dir: Path | None = None)` — when `static_dir` exists, mounts it at `/` (SPA index fallback); API routes keep priority.

- [ ] **Step 1: Write the failing test** (append to `tests/test_app.py`)

```python
def test_serves_static_index(tmp_path):
    from capevolve_dashboard.app import create_app
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>cap-evolve</title>", encoding="utf-8")
    base = tmp_path / "runs"
    base.mkdir()
    c = TestClient(create_app(base, static_dir=static))
    r = c.get("/")
    assert r.status_code == 200
    assert "cap-evolve" in r.text
    # API still wins
    assert c.get("/api/health").json()["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_app.py::test_serves_static_index -v`
Expected: FAIL — `create_app() got an unexpected keyword argument 'static_dir'`.

- [ ] **Step 3: Update `create_app` signature + mount** in `app.py`

Change the signature to `def create_app(base_dir: Path, static_dir: Path | None = None) -> FastAPI:` and, just before `return app`, add:

```python
    if static_dir is not None and Path(static_dir).is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard/backend && python -m pytest tests/test_app.py -v`
Expected: PASS (all in file).

- [ ] **Step 5: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/app.py dashboard/backend/tests/test_app.py
git commit -m "feat(dashboard): serve built SPA assets when present"
```

---

### Task 7: Idempotent launch helper + CLI entrypoint

**Files:**
- Create: `dashboard/backend/capevolve_dashboard/server.py`
- Create: `dashboard/backend/README.md`
- Test: `dashboard/backend/tests/test_server.py`

**Interfaces:**
- Produces:
  - `server.is_up(port: int, host: str = "127.0.0.1") -> bool` — `True` if `GET /api/health` succeeds.
  - `server.resolve_static_dir() -> Path | None` — `<repo>/dashboard/frontend/dist` if built, else `None`.
  - `server.ensure_up(base_dir, port=7878, open_browser=True) -> str` — returns the URL; if already up, no-op; else spawns Uvicorn in a background process. (Pure-logic parts are unit-tested; process spawn is integration-only.)
  - `server.main(argv=None) -> int` — CLI: `cap-evolve-dashboard --base .capevolve --port 7878 [--no-open]`.

- [ ] **Step 1: Write the failing test** in `tests/test_server.py`

```python
def test_is_up_false_when_nothing_listening():
    from capevolve_dashboard import server
    # Port 1 is never an http health endpoint; should be quick-false.
    assert server.is_up(1) is False


def test_resolve_static_dir_returns_path_or_none():
    from capevolve_dashboard import server
    out = server.resolve_static_dir()
    assert out is None or out.name == "dist"


def test_url_for():
    from capevolve_dashboard import server
    assert server.url_for(7878) == "http://127.0.0.1:7878"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard/backend && python -m pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capevolve_dashboard.server'`.

- [ ] **Step 3: Write `server.py`**

```python
"""Idempotent launcher for the dashboard server + CLI entrypoint."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path


def url_for(port: int, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{port}"


def is_up(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with urllib.request.urlopen(f"{url_for(port, host)}/api/health", timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False


def resolve_static_dir() -> Path | None:
    # server.py -> capevolve_dashboard -> backend -> dashboard -> repo
    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    return dist if dist.is_dir() else None


def ensure_up(base_dir, port: int = 7878, open_browser: bool = True) -> str:
    url = url_for(port)
    if is_up(port):
        if open_browser:
            webbrowser.open(url)
        return url
    env = dict(os.environ, CAPEVOLVE_BASE_DIR=str(base_dir), CAPEVOLVE_PORT=str(port))
    static = resolve_static_dir()
    if static:
        env["CAPEVOLVE_STATIC_DIR"] = str(static)
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "capevolve_dashboard.asgi:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if open_browser:
        webbrowser.open(url)
    return url


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cap-evolve-dashboard")
    p.add_argument("--base", default=".capevolve")
    p.add_argument("--port", type=int, default=7878)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args(argv)
    url = ensure_up(args.base, port=args.port, open_browser=not args.no_open)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `asgi.py`** (module Uvicorn imports; reads env set by `ensure_up`)

Create `dashboard/backend/capevolve_dashboard/asgi.py`:

```python
"""ASGI entrypoint: builds the app from env vars (used by uvicorn)."""
import os
from pathlib import Path

from .app import create_app

_base = Path(os.environ.get("CAPEVOLVE_BASE_DIR", ".capevolve"))
_static = os.environ.get("CAPEVOLVE_STATIC_DIR")
app = create_app(_base, static_dir=Path(_static) if _static else None)
```

- [ ] **Step 5: Write `README.md`** (`dashboard/backend/README.md`)

```markdown
# cap-evolve dashboard — backend

FastAPI service over cap-evolve run dirs. Read-only; reuses `cap_evolve.dashboard.reduce_run`.

## Dev
    pip install -e ../../core        # cap-evolve-core
    pip install -e .[dev]
    python -m pytest -q

## Run
    cap-evolve-dashboard --base .capevolve --port 7878
    # serves the built frontend (dashboard/frontend/dist) when present
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd dashboard/backend && python -m pytest tests/test_server.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Full backend test sweep**

Run: `cd dashboard/backend && python -m pytest -q`
Expected: PASS (all tasks' tests green).

- [ ] **Step 8: Commit**

```bash
git add dashboard/backend/capevolve_dashboard/server.py dashboard/backend/capevolve_dashboard/asgi.py dashboard/backend/README.md dashboard/backend/tests/test_server.py
git commit -m "feat(dashboard): idempotent launch helper + ASGI entrypoint + CLI"
```

---

## Self-Review

**Spec coverage (Plan 1 portion):** Backend (§5) ✓ — discovery, `/api/runs`, `/api/runs/{id}`, rollouts, diff, compare, SSE live, static serving, launch helper. Single-sourced contract via `reduce_run` ✓. Read-only ✓. Redaction preserved ✓ (reuse `redact`/reducer). Hub/compare data (§6, §7) ✓ projected. Trajectories/diffs/memory raw data exposed for the frontend (§8) ✓ (memory files like `MEMORY.md`/`STATE.md` are served from `candidates/<id>/` via a generic candidate-file read — see "Deferred to plan note" below).

**Gap noted & folded in:** the frontend's **Memory** tab needs `candidates/<id>/MEMORY.md` / `STATE.md`. This is a one-route addition; it is intentionally deferred to **Plan 4 (integration)** alongside the candidate-snapshot reader, to keep Plan 1 focused on the reduced-graph contract. Flagged here so it is not lost.

**Placeholder scan:** No TBD/TODO. The one "confirm against `build_diffs`" note (Task 3 Step 3) is a verification instruction with a concrete fallback shape, not a placeholder.

**Type consistency:** `runs.load_run`/`RunNotFound` used consistently in app/compare/stream; `create_app(base_dir, static_dir=None)` signature consistent across Tasks 2/6; `sse_format`/`read_new_events` signatures match their tests; `ensure_up`/`is_up`/`url_for`/`resolve_static_dir` consistent in Task 7 + tests.

---

## Downstream plans (written when their turn comes — they depend on this plan's final API shapes)

- **Plan 2 — Frontend shell & core views:** Vite + React + TS + Tailwind + shadcn/ui (21st MCP) + Recharts; capybara brand + dark-OLED evolve theme; SSE client; Hub; Run **Overview** (KPI strip + cumulative-best chart); **Lineage** (best-path spine).
- **Plan 3 — Explainability views:** Phases timeline, Trajectories, Iterations (diffs), Memory, Insights (what-helped/didn't, tool usage, dead-ends, narrative summary), Compare page.
- **Plan 4 — Pipeline & CLI integration:** candidate-file/memory route; `cap-evolve dashboard` subcommand; auto-start at pipeline start in `cli.py:_cmd_run` (default on, `dashboard: auto|report-only|off`, `--dashboard/--no-dashboard/--dashboard-port`); report-phase `ensure_up` + open + pin final view.
- **Plan 5 — Improve the legacy single-file `dashboard.html`:** capybara logo + evolve theme; expanded KPI strip; phases timeline; "What Not To Try" dead-ends panel; narrative summary — all within the stdlib-only zero-dependency constraint.
