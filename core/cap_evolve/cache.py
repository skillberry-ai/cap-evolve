"""Eval cache — skip a rollout when the same candidate was already scored on a task.

Keyed by ``(hash of the candidate's editable files, task_id) ->
{reward, feedback, rollout_file}`` and persisted in the run dir, so re-evaluating an
identical candidate (e.g. a parent re-sampled in GEPA, or a resumed run) costs nothing.
The hash is over file CONTENTS, so two byte-identical candidates share cache entries
even under different ids.

``rollout_file`` (#111) names the rollout json, under ``rollouts/<split>/``, that
PRODUCED this cached score. GEPA's reflective dataset — its entire learning signal —
needs the agent's ``output``/``trace``, not just the number; a score-only hit made
``REFLECTION.md`` emit ``Agent output:`` (empty) for cached failing tasks and quietly
degraded GEPA to a blind hill-climb on cached parents. Storing a POINTER rather than
the payload keeps the cache small (~40 bytes/entry) and the reflection UNTRUNCATED:
the rollout json is already persisted in the run dir, so a hit re-reads the real
record instead of a redacted copy of it. A hit whose pointer no longer resolves is
treated as a MISS by the reflection-bearing caller, so a score-only entry can never
hollow out a reflective dataset again.

Honesty notes:
  * The cache stores only the SCORE (reward + feedback) plus a pointer to the
    already-persisted rollout json, never gold answers.
  * It is keyed on candidate-file content, so an edit (even whitespace) busts the
    key — a stale score can never be served for changed files.
  * It is an optimization, not a source of truth: ``events.jsonl`` still records
    every evaluation. Wiring into ``evaluate_candidate`` is OFF by default and gated
    behind a flag (see ``maybe_cached_score``) so it cannot silently change behavior.

Pure stdlib (hashlib + json).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Files that are NOT part of the capability (optimizer scratch, memory, vcs); they
# must not perturb the content hash or every iteration would miss the cache.
_IGNORE_NAMES = {"MEMORY.md", "STATE.md", "INSTRUCTIONS.md", "REJECTED.md", "FOCUS.md",
                 "REFLECTION.md",
                 # cross-iteration state files (clean-ownership redesign) — scratch, not capability
                 "LEDGER.md", "JOURNAL.md", "PROCESS.md", "RUNMAP.md"}
_IGNORE_DIRS = {".git", "__pycache__", "prior_iterations"}


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

    ``get(candidate_hash, task_id)`` -> ``{"reward", "feedback"}`` plus an OPTIONAL
    ``"rollout_file"`` (omitted when unknown — e.g. a pre-#111 entry; readers treat its
    absence as a miss), or ``None``;
    ``put(candidate_hash, task_id, reward, feedback, rollout_file=...)``
    persists. Persistence is a single JSON object ``{ "<hash>::<task_id>": {...} }``
    rewritten on each put — fine for the run sizes here (a few thousand entries) and
    trivially portable.
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
            rollout_file: str = "") -> None:
        """Persist a score. ``rollout_file`` is the ``rollouts/<split>/`` filename whose
        json holds the rollout behind this score, so a later hit can rebuild the full
        reflective signal (output + trace) instead of only the number (#111)."""
        entry = {"reward": float(reward), "feedback": str(feedback or "")}
        if rollout_file:
            entry["rollout_file"] = str(rollout_file)
        self._data[self._key(candidate_hash, task_id)] = entry
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
