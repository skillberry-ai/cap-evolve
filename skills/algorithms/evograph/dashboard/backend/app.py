"""EvoGraph dashboard backend — a read-only view over a cap-evolve run dir.

Agents never call this. It only reads the files under EVOGRAPH_BASE (the cap-evolve run dir the
evograph skill writes its wiki into) and serves them as JSON + SSE, plus the prebuilt React app at "/".

File layout it reads (see skills/algorithms/evograph/references/dashboard.md):
  wiki/weaknesses/<slug>.md
  wiki/solutions/<weakness-slug>/<sol-id>/{solution.md,changes.diff}
  wiki/results/round-<N>.json | final-test.json
  runs/round-<N>/agents/<slug>.log
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(os.environ.get("EVOGRAPH_BASE", ".")).resolve()
DIST = Path(os.environ.get("EVOGRAPH_DIST", "")).resolve() if os.environ.get("EVOGRAPH_DIST") else None

WIKI = BASE / "wiki"
WEAK = WIKI / "weaknesses"
SOLS = WIKI / "solutions"
RESULTS = WIKI / "results"
RUNS = BASE / "runs"

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
# Rejected Store Memory entries look like:  ### Round 2 · `raise-temperature`
RSM_HEADING = re.compile(r"^#{2,4}\s+(.*)$")
ROUND_IN_TEXT = re.compile(r"round\s*(\d+)", re.IGNORECASE)

app = FastAPI(title="EvoGraph dashboard", docs_url=None, redoc_url=None)


# --------------------------------------------------------------------------- path safety
# Route params (slug / weakness / sol_id) name a single file or directory under the
# run dir, and they are user-controlled. We never join them onto a path: instead we
# enumerate the fixed parent directory and return the child whose *name* equals the
# requested segment. The served path therefore always originates from a filesystem
# listing, so traversal payloads ("..", "/etc/passwd", absolute paths) simply never
# match anything and can never widen what the server reads.
def child_named(base: Path, name: str) -> Path | None:
    """Return the direct child of ``base`` whose name is exactly ``name`` (by listing
    ``base``, not by path-joining untrusted input), or None if there is no such child."""
    if not base.is_dir():
        return None
    for child in base.iterdir():
        if child.name == name:
            return child
    return None


# --------------------------------------------------------------------------- helpers
def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return (front_matter_dict, body_markdown). Tolerant of missing/invalid front-matter."""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def read_md(path: Path) -> tuple[dict[str, Any], str]:
    return split_front_matter(path.read_text(encoding="utf-8-sig"))


def round_key(p: Path) -> tuple[int, int]:
    """Sort key for results files: numbered rounds first (by N), final-test last."""
    if p.stem.startswith("round-"):
        try:
            return (0, int(p.stem.split("-")[1]))
        except (IndexError, ValueError):
            return (0, 0)
    return (1, 0)  # final-test


def list_solution_dirs(weakness_slug: str) -> list[Path]:
    d = SOLS / weakness_slug
    if not d.is_dir():
        return []
    return sorted([p for p in d.iterdir() if p.is_dir() and (p / "solution.md").exists()])


def load_solution(weakness_slug: str, sol_dir: Path) -> dict[str, Any]:
    fm, body = read_md(sol_dir / "solution.md")
    return {
        "id": sol_dir.name,
        "weakness": weakness_slug,
        "front_matter": fm,
        "markdown": body,
        "outcome": fm.get("outcome"),
        "primary_metric": fm.get("primary_metric"),
        "secondary_metrics": fm.get("secondary_metrics", []),
        "new_record": bool(fm.get("new_record", False)),
        "timestamp": fm.get("timestamp"),
    }


def load_all_results() -> list[dict[str, Any]]:
    if not RESULTS.is_dir():
        return []
    out = []
    for p in sorted(RESULTS.glob("*.json"), key=round_key):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8-sig")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


VALUE_IN_TEXT = re.compile(r"[-+]?\d*\.?\d+")


def parse_rejected(body: str) -> list[dict[str, Any]]:
    """Pull rejected attempts from the weakness md's 'Rejected Store Memory' section.

    Returns each as {label, round, value}. `value` is the metric the attempt reached on the
    weakness's tasks, parsed from a "Result: reward 0.48 …"-style line if present (else None).
    Tolerant: if there's no RSM section, returns [].
    """
    lower = body.lower()
    idx = lower.find("rejected store memory")
    if idx == -1:
        return []
    section = body[idx:]
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in section.splitlines():
        m = RSM_HEADING.match(line.strip())
        if m and "rejected store memory" not in m.group(1).lower():
            heading = m.group(1).strip()
            rnd = ROUND_IN_TEXT.search(heading)
            # Only real attempts are entries — they carry a round number (e.g.
            # "Round 2 · raise-temperature"). Skip section/format headings like
            # "RSM entry format" that would otherwise become bogus rejected attempts.
            if not rnd:
                current = None
                continue
            current = {
                "label": heading.replace("`", "").replace("·", "-").strip(),
                "round": int(rnd.group(1)),
                "value": None,
            }
            out.append(current)
        elif current is not None and current["value"] is None:
            low = line.lower()
            if any(k in low for k in ("result", "reward", "metric", "value", "→", "->")):
                num = VALUE_IN_TEXT.search(line)
                if num:
                    try:
                        current["value"] = float(num.group())
                    except ValueError:
                        pass
    return out


LEADING_TIME = re.compile(r"^\s*\d{1,2}:\d{2}(:\d{2})?\b")


def stamp_line(line: str) -> str:
    """Prefix a log line with the dashboard machine's LOCAL time (the user's timezone),
    unless the agent already wrote a leading HH:MM[:SS]."""
    if LEADING_TIME.match(line):
        return line
    return f"{datetime.now().strftime('%H:%M:%S')}  {line}"


def latest_log_for(slug: str) -> Path | None:
    """Most recent runs/round-*/agents/<slug>.log.

    Enumerate every agent log (fixed glob, no user input in the pattern) and keep the
    ones whose filename matches ``<slug>.log`` — so the path we tail always comes from
    the directory listing, never from concatenating the user-supplied slug."""
    if not RUNS.is_dir():
        return None
    target = f"{slug}.log"
    candidates = sorted(
        (p for p in RUNS.glob("round-*/agents/*.log") if p.name == target),
        key=lambda p: round_key(p.parent.parent),
    )
    return candidates[-1] if candidates else None


# --------------------------------------------------------------------------- API
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "base": str(BASE), "wiki_exists": WIKI.exists()}


def normalize_related(raw: Any) -> list[dict[str, Any]]:
    """`related` may be a list of slugs or of {slug, why} dicts; normalize to dicts."""
    out = []
    for item in raw or []:
        if isinstance(item, str):
            out.append({"slug": item, "why": None})
        elif isinstance(item, dict) and item.get("slug"):
            out.append({"slug": item["slug"], "why": item.get("why")})
    return out


@app.get("/api/graph")
def graph() -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    if WEAK.is_dir():
        for p in sorted(WEAK.glob("*.md")):
            fm, _ = read_md(p)
            slug = fm.get("slug", p.stem)
            sols = [load_solution(slug, d) for d in list_solution_dirs(slug)]
            best = None
            for s in sols:
                pm = s.get("primary_metric") or {}
                if isinstance(pm, dict) and isinstance(pm.get("value"), (int, float)):
                    best = pm["value"] if best is None else max(best, pm["value"])
            nodes.append({
                "slug": slug,
                "status": fm.get("status", "open"),
                "tags": fm.get("tags", []),
                "discovered_in_round": fm.get("discovered_in_round"),
                "attacked_in_rounds": fm.get("attacked_in_rounds", []),
                "num_affected_tasks": len(fm.get("affected_tasks", []) or []),
                "num_solutions": len(sols),
                "has_record": any(s["new_record"] for s in sols),
                "best_primary_metric": best,
                "related": normalize_related(fm.get("related")),
            })
    # weakness <-> weakness edges from `related` (undirected, deduped, only between real nodes)
    known = {n["slug"] for n in nodes}
    seen: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []
    for n in nodes:
        for r in n["related"]:
            tgt = r["slug"]
            if tgt not in known or tgt == n["slug"]:
                continue
            key = tuple(sorted((n["slug"], tgt)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": n["slug"], "target": tgt, "why": r.get("why")})
    return {"nodes": nodes, "edges": edges}


@app.get("/api/weakness/{slug}")
def weakness(slug: str) -> dict[str, Any]:
    p = child_named(WEAK, f"{slug}.md")
    if p is None or not p.is_file():
        raise HTTPException(404, f"weakness '{slug}' not found")
    fm, body = read_md(p)
    affected = set(fm.get("affected_tasks", []) or [])
    # per-task metric history across rounds, restricted to this weakness's tasks
    history = []
    for res in load_all_results():
        rows = [r for r in res.get("per_task", []) if str(r.get("task_id")) in {str(a) for a in affected}]
        if rows:
            history.append({"round": res.get("round"), "split": res.get("split"), "per_task": rows})
    sols = [load_solution(slug, d) for d in list_solution_dirs(slug)]
    return {"slug": slug, "front_matter": fm, "markdown": body, "solutions": sols,
            "rejected_attempts": parse_rejected(body), "task_history": history}


@app.get("/api/solution/{weakness}/{sol_id}")
def solution(weakness: str, sol_id: str) -> dict[str, Any]:
    weak_dir = child_named(SOLS, weakness)
    sol_dir = child_named(weak_dir, sol_id) if weak_dir is not None else None
    if sol_dir is None or not (sol_dir / "solution.md").is_file():
        raise HTTPException(404, f"solution '{weakness}/{sol_id}' not found")
    data = load_solution(weakness, sol_dir)
    diff_path = child_named(sol_dir, "changes.diff")
    data["diff"] = diff_path.read_text(encoding="utf-8-sig") if diff_path is not None else ""
    return data


@app.get("/api/results")
def results() -> dict[str, Any]:
    return {"results": load_all_results()}


@app.get("/api/run-config")
def run_config() -> dict[str, Any]:
    """The run's `.evograph/run-config.json`, if the user dropped one in. Optional and free-form:
    the UI renders whatever JSON is there and shows nothing if it's absent."""
    p = BASE / "run-config.json"
    rel = "run-config.json"
    if not p.exists():
        return {"exists": False, "config": None, "path": rel}
    try:
        cfg = json.loads(p.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        # Don't leak filesystem paths / stack detail to the client; the message is fixed.
        return {"exists": True, "config": None, "path": rel,
                "error": "run-config.json could not be read or parsed"}
    return {"exists": True, "config": cfg, "path": rel}


@app.get("/api/progress/{slug}/stream")
async def progress_stream(slug: str) -> StreamingResponse:
    log = latest_log_for(slug)

    async def gen():
        # emit whatever exists, then tail for new lines
        pos = 0
        # re-resolve each loop so a log appearing mid-run is picked up
        nonlocal log
        while True:
            cur = log or latest_log_for(slug)
            if cur and cur.exists():
                log = cur
                with cur.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                if chunk:
                    for line in chunk.splitlines():
                        yield f"data: {stamp_line(line)}\n\n"
            else:
                yield ": waiting for log\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


# --------------------------------------------------------------------------- static SPA
if DIST and DIST.exists():
    _dist: Path = DIST
    # Serve assets and fall back to index.html for client-side routes.
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_dist / "index.html"))

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # Client-side routes all resolve to the SPA entrypoint. Real static files are
        # served by the /assets mount above; this handler never reads a user-named
        # path, so there is no traversal surface here.
        return FileResponse(str(_dist / "index.html"))
