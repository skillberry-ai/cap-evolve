"""Eval cache — skip a rollout when the same candidate was already scored on a task.

Keyed by ``(hash of the candidate's editable files, task_id) ->
{reward, feedback, output, trace, errored}``
and persisted in the run dir, so re-evaluating an identical candidate (e.g. a parent
re-sampled in GEPA, or a resumed run) costs nothing. The hash is over file CONTENTS,
so two byte-identical candidates share cache entries even under different ids.

Honesty notes:
  * The cache stores the SCORE (reward + feedback) plus a bounded slice of the
    agent's OWN output/trace (truncated by the caller, ~1.5KB each) so a hit yields
    the same reflective material as a miss. Never gold answers.
  * It is keyed on candidate-file content, so an edit (even whitespace) busts the
    key — a stale score can never be served for changed files.
  * It is an optimization, not a source of truth: ``events.jsonl`` still records
    every evaluation.
  * Scope: GEPA only. ``gepa`` constructs one cache and consults it inside its
    minibatch eval; ``harness.evaluate_candidate`` never touches it, so a plain
    hill-climb / skillopt run is unaffected.

Pure stdlib (hashlib + json).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Files that are NOT part of the capability (optimizer scratch, memory, vcs); they
# must not perturb the content hash or every iteration would miss the cache.
from .types import NON_CAPABILITY_DIRS as _IGNORE_DIRS  # noqa: E402
from .types import NON_CAPABILITY_FILES as _IGNORE_NAMES  # noqa: E402


def hash_candidate_dir(candidate_dir: Path) -> str:
    """Stable SHA-256 over the candidate's editable files (path + content).

    Walks ``candidate_dir`` deterministically (sorted relative paths), skipping
    optimizer-scratch files and vcs/cache dirs, and folds each file's relative path
    and bytes into the digest. Two dirs with identical editable content hash equal
    regardless of mtime or traversal order.
    """
    cdir = Path(candidate_dir)
    h = hashlib.sha256()
    if not cdir.exists():
        return h.hexdigest()
    files = []
    for p in cdir.rglob("*"):
        if not p.is_file():
            continue
        if p.name in _IGNORE_NAMES:
            continue
        if any(part in _IGNORE_DIRS for part in p.relative_to(cdir).parts):
            continue
        files.append(p)
    for p in sorted(files, key=lambda x: str(x.relative_to(cdir))):
        rel = str(p.relative_to(cdir)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


class EvalCache:
    """A tiny JSON-file eval cache living in the run dir.

    ``get(candidate_hash, task_id)`` -> the stored entry or ``None``;
    ``put(...)`` persists. Persistence is a
    single JSON object ``{ "<hash>::<task_id>": {...} }`` rewritten on each put — fine
    for the run sizes here (a few thousand entries) and trivially portable.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except (json.JSONDecodeError, OSError):
                self._data = {}

    @staticmethod
    def _key(candidate_hash: str, task_id: str) -> str:
        return f"{candidate_hash}::{task_id}"

    def get(self, candidate_hash: str, task_id: str) -> dict | None:
        return self._data.get(self._key(candidate_hash, task_id))

    def put(self, candidate_hash: str, task_id: str, reward: float, feedback: str = "",
            output: str = "", trace: str = "", errored: bool = False) -> None:
        # ponytail: callers pass output/trace ALREADY truncated (gepa._short, 1500 chars),
        # so an entry stays ~3KB; _flush rewrites the whole file per put, which is fine at
        # these run sizes. Add eviction only if a run's cache file ever gets unwieldy.
        self._data[self._key(candidate_hash, task_id)] = {
            "reward": float(reward), "feedback": str(feedback or ""),
            "output": str(output or ""), "trace": str(trace or ""),
            "errored": bool(errored)}
        self._flush()

    def _flush(self) -> None:
        # Atomic-ish write (tmp + replace) so a crash mid-write can't corrupt the cache.
        import os
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.tmp.{os.getpid()}")
        tmp.write_text(json.dumps(self._data), encoding="utf-8")
        os.replace(tmp, self.path)

    def __len__(self) -> int:
        return len(self._data)
