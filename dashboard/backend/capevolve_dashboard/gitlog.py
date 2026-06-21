"""Git iteration history + real diffs between commits in a run dir's store.

cap-evolve's default ``git`` store commits after every iteration, so the run dir is a
browsable history. We expose the commit log and the unified diff between any two
commits, projected into the same ``{t, l}`` row shape the candidate-snapshot diff
renderer already uses (``t`` is ``add|del|ctx|hunk``).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from cap_evolve import dashboard

import string

# Commit refs we accept (sha-ish, HEAD, HEAD~n, branch/tag names). Args are passed as
# a list (no shell), but we still reject anything odd and any leading '-' so a ref
# can't be read as a git option.
_RANGE_OK = set(string.ascii_letters + string.digits + "~^/_-.")


def _has_git(root: Path) -> bool:
    return (Path(root) / ".git").exists() and shutil.which("git") is not None


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args],
                       capture_output=True, text=True, timeout=15)
    return r.stdout if r.returncode == 0 else ""


def log(run_path: Path, limit: int = 200) -> list[dict]:
    """One row per iteration commit: ``{hash, subject, iter}`` (oldest first)."""
    root = Path(run_path)
    if not _has_git(root):
        return []
    out = _git(root, "log", f"-n{int(limit)}", "--format=%h%x09%s")
    rows = []
    for line in out.splitlines():
        if "\t" in line:
            h, s = line.split("\t", 1)
            rows.append({"hash": h, "subject": s})
    rows.reverse()
    for i, r in enumerate(rows):
        r["iter"] = i
    return rows


def _valid_ref(ref: str) -> bool:
    return (bool(ref) and not ref.startswith("-") and len(ref) <= 64
            and all(c in _RANGE_OK for c in ref))


def diff(run_path: Path, frm: str, to: str) -> dict:
    """Unified diff ``frm..to`` parsed into per-file add/remove rows."""
    root = Path(run_path)
    if not _has_git(root):
        return {"from": frm, "to": to, "files": [], "available": False}
    if not (_valid_ref(frm) and _valid_ref(to)):
        return {"from": frm, "to": to, "files": [], "error": "bad ref"}
    raw = _git(root, "diff", "--unified=3", f"{frm}", f"{to}")
    files: list[dict] = []
    cur: dict | None = None
    for line in raw.splitlines():
        if line.startswith("diff --git"):
            if cur:
                files.append(cur)
            cur = {"path": line.split(" b/")[-1], "added": 0, "removed": 0, "rows": []}
            continue
        if cur is None:
            continue
        if line.startswith(("index ", "--- ", "+++ ")):
            continue
        if line.startswith("@@"):
            cur["rows"].append({"t": "hunk", "l": line})
        elif line.startswith("+"):
            cur["added"] += 1
            cur["rows"].append({"t": "add", "l": line[1:]})
        elif line.startswith("-"):
            cur["removed"] += 1
            cur["rows"].append({"t": "del", "l": line[1:]})
        else:
            cur["rows"].append({"t": "ctx", "l": line[1:] if line.startswith(" ") else line})
    if cur:
        files.append(cur)
    return dashboard.redact({"from": frm, "to": to, "files": files, "available": True})
