"""Read optimizer memory (accepted history, rejected memory) and per-candidate
scratch files from a run dir. Read-only; everything passes through redact()."""
from __future__ import annotations

import json
from pathlib import Path

from cap_evolve import dashboard

_SCRATCH_SUFFIXES = {".md", ".txt"}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read_memory(run_path: Path) -> dict:
    root = Path(run_path)
    return dashboard.redact({
        "history": _read_jsonl(root / "history.jsonl"),
        "rejected": _read_jsonl(root / "rejected.jsonl"),
    })


def list_candidate_files(run_path: Path, candidate_id: str) -> list[dict]:
    """Return the scratch/capability files snapshotted for a candidate.

    `candidate_id` is reduced to a single path segment to prevent traversal.
    """
    safe = Path(candidate_id).name
    cdir = Path(run_path) / "candidates" / safe
    if not cdir.is_dir():
        return []
    files = []
    for f in sorted(cdir.iterdir()):
        if f.is_file() and f.suffix in _SCRATCH_SUFFIXES:
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            files.append({"name": f.name, "text": text})
    return dashboard.redact(files)
