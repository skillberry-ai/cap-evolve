"""Generic, format-agnostic directory browser for a run dir.

The Memory/Files view shows whatever is actually on disk (the memory directory, the
candidates, the work tree, the store) without assuming any schema. Every path is
confined to the run dir, text-only, size-capped, and redacted — the same guarantees
as the rest of the read-only API.
"""
from __future__ import annotations

from pathlib import Path

from cap_evolve import dashboard

# Directories that are huge/noisy and not useful to browse as a tree.
_SKIP_DIRS = {".git", "__pycache__", ".state.lock"}
_MAX_FILE_BYTES = 256 * 1024
_MAX_ENTRIES = 4000


def _safe_join(run_path: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``run_path``, rejecting any escape (``..``, symlinks)."""
    root = Path(run_path).resolve()
    target = (root / (rel or "")).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(rel)
    return target


def _looks_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    # crude heuristic: a high share of non-text bytes
    text = bytes(range(0x20, 0x7F)) + b"\n\r\t\f\b"
    nontext = sum(1 for b in data[:1024] if b not in text)
    return len(data) > 0 and nontext / min(len(data), 1024) > 0.30


def tree(run_path: Path, rel: str = "") -> dict:
    """A recursive listing of ``rel`` under the run dir.

    Returns ``{"path", "entries": [{"name","path","type","size","children"?}]}``.
    ``type`` is ``dir`` or ``file``; dirs carry nested ``children``. Bounded by
    ``_MAX_ENTRIES`` so a pathological tree can't hang the UI.
    """
    base = _safe_join(run_path, rel)
    root = Path(run_path).resolve()
    budget = [_MAX_ENTRIES]

    def walk(d: Path) -> list[dict]:
        out: list[dict] = []
        if budget[0] <= 0:
            return out
        try:
            children = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return out
        for p in children:
            if p.name in _SKIP_DIRS or budget[0] <= 0:
                continue
            budget[0] -= 1
            relpath = str(p.relative_to(root))
            if p.is_dir():
                out.append({"name": p.name, "path": relpath, "type": "dir",
                            "children": walk(p)})
            elif p.is_file():
                try:
                    size = p.stat().st_size
                except OSError:
                    size = None
                out.append({"name": p.name, "path": relpath, "type": "file", "size": size})
        return out

    entries = walk(base) if base.is_dir() else []
    return {"path": str(base.relative_to(root)) if base != root else "", "entries": entries,
            "truncated": budget[0] <= 0}


def read_file(run_path: Path, rel: str) -> dict:
    """Return one text file's contents (size-capped, binary-detected, redacted)."""
    target = _safe_join(run_path, rel)
    if not target.is_file():
        raise FileNotFoundError(rel)
    raw = target.read_bytes()
    truncated = len(raw) > _MAX_FILE_BYTES
    chunk = raw[:_MAX_FILE_BYTES]
    if _looks_binary(chunk):
        return {"path": rel, "binary": True, "size": len(raw), "text": None}
    text = chunk.decode("utf-8", errors="replace")
    return dashboard.redact({"path": rel, "binary": False, "size": len(raw),
                             "truncated": truncated, "text": text})
