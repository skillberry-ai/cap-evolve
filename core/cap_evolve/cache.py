"""Eval cache — skip a rollout when the same candidate was already scored on a task.

Keyed by ``(hash of the candidate's editable files, task_id) -> {reward, feedback}``
and persisted in the run dir, so re-evaluating an identical candidate (e.g. a parent
re-sampled in GEPA, or a resumed run) costs nothing. The hash is over file CONTENTS,
so two byte-identical candidates share cache entries even under different ids.

**Scope: GEPA only** — which bounds the "costs nothing" above. The single consumer is
``gepa._eval_minibatch``, where the same parent is re-sampled from the Pareto frontier
across iterations and re-scored on overlapping minibatches; that repetition is what the
cache pays for. ``harness.evaluate_candidate`` (every full-val and sealed-test eval, in
every algorithm) does NOT consult it and always pays full price, so re-scoring an
identical candidate on full val — including on ``--resume`` or a seed re-eval — is NOT
deduplicated. Wiring it in there is a possible perf win, not existing behavior, and
there is no flag for it today (``test_w1_engine.py`` guards that claim).

Honesty notes:
  * The cache stores only the SCORE (reward + feedback), never gold answers.
  * It is keyed on candidate-file content, so an edit (even whitespace) busts the
    key — a stale score can never be served for changed files.
  * It is an optimization, not a source of truth: ``events.jsonl`` still records
    every evaluation.

Pure stdlib (hashlib + json).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .optimizer_context import INJECTED_DIRS, INJECTED_NAMES
from .rundir import NON_CAPABILITY_NAMES

# Files that are NOT part of the capability (optimizer scratch, memory, vcs); they
# must not perturb the content hash or every iteration would miss the cache.
# ``rundir.NON_CAPABILITY_NAMES`` is the shared definition (see the note there): the
# union of live + legacy scratch plus INSTRUCTIONS/PROCESS, which ARE snapshotted but
# still are not capability bytes. This is a read-side filter (skip bytes when hashing),
# so it takes the whole union — including the legacy names, so caches written before
# they were retired keep resolving. The INJECTED_* halves are the optimizer-context
# read-context (``trajectories/``, ``guidance/``, the native per-agent skill dirs and
# instructions files) — one definition in ``optimizer_context``, folded in as a plain
# constant expression (no import-time set mutation, so no import-order dependence).
_IGNORE_NAMES = set(NON_CAPABILITY_NAMES) | set(INJECTED_NAMES)
_IGNORE_DIRS = {".git", "__pycache__"} | set(INJECTED_DIRS)


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
        rel = p.relative_to(cdir)
        # Root-anchored: every ignored name is a root-level framework injection, so a
        # NESTED file that merely shares one (``src/prompts/STATE.md``) is capability
        # content and MUST fold into the digest — otherwise deleting it leaves the hash
        # unchanged and the next iteration serves the parent's cached rewards for a
        # materially different candidate (a stale hit on a mutilated candidate).
        if len(rel.parts) == 1 and p.name in _IGNORE_NAMES:
            continue
        if any(part in _IGNORE_DIRS for part in rel.parts):
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

    ``get(candidate_hash, task_id)`` -> ``{"reward", "feedback"}`` or ``None``;
    ``put(candidate_hash, task_id, reward, feedback)`` persists. Persistence is a
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

    def put(self, candidate_hash: str, task_id: str, reward: float, feedback: str = "") -> None:
        self._data[self._key(candidate_hash, task_id)] = {
            "reward": float(reward), "feedback": str(feedback or "")}
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
