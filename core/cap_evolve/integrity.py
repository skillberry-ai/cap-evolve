"""Protected-path tamper detection — a host-independent seal on the eval surface.

cap-evolve hands a candidate directory to an LLM optimizer and then measures it.
Nothing *structurally* stops that optimizer from editing the evaluation harness,
the gold answers, or the task data instead of improving the capability — the
classic reward-hacking failure of every agentic optimizer. Today the only defense
is the Claude-Code ``PreToolUse`` hook (``plugins/cap-evolve/hooks/deny_sealed_edits.py``),
which does nothing when the optimizer is Codex, Gemini, a bare shell, or anything
else in ``skills/optimizers/registry.yaml``. A content-hash manifest does not care
which host ran the edit, so it is strictly stronger.

Usage is two calls around the optimizer::

    man = snapshot(project_dir, patterns)      # before the optimizer runs
    ...
    report = verify(man, project_dir)          # before the gate decides
    if not report.ok: discard the candidate    # NOT score 0.0 — see below

Semantics that matter
---------------------
**Tamper means the score is not data.** A tampered candidate must be *discarded*,
never recorded as ``reward=0.0``. cap-evolve already draws this line for
infrastructure faults: ``harness._persist_trial`` treats an errored trial as
missing data, ``loop.aggregate_scores`` drops tasks with zero valid trials, and
``gate.decide`` returns ``indecisive`` rather than a rejection when coverage is
too low. A tampered measurement is the same category — the number describes a
compromised harness, not the edit — and folding a 0.0 into the mean would poison
both the split mean and the paired gate. Mirror the ``indecisive`` vocabulary:
this is a measurement problem, not a verdict on the candidate's content.

**Added files count as tampering.** Dropping a shadowing ``conftest.py`` next to
the real one, or a second gold file the scorer might pick up, is a real attack
and shows up only as an addition.

**Same glob semantics at snapshot time and verify time.** Both sides route
through :func:`_match`, so runtime enforcement and accept-time enforcement can
never disagree about what "protected" means.

**Symlinks are never followed out of ``root``.** A symlink is hashed by its
*target string*, so a retargeted link reads as ``modified`` and a link pointing
outside the tree can't be used to hash (or smuggle in) foreign bytes. Every path
is ``resolve()`` + ``relative_to(root)`` hardened before it enters the manifest.

Pure stdlib.
"""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .rundir import _atomic_write

VERSION = 1
_CHUNK = 1 << 20  # 1 MiB: stream, so a multi-GB task file can't blow memory

#: Sensible default protections for a cap-evolve project. Callers should pass
#: their own; this is what the wiring uses when the project declares nothing.
DEFAULT_PATTERNS: tuple[str, ...] = (
    "*gold*",
    "*answer*key*",
    "tasks/*",
    "data/*",
    "tests/*",
    "conftest.py",
    "*/conftest.py",
    "scorer.py",
    "*/scorer.py",
    "adapter.py",
    "*/adapter.py",
    "splits.json",
)


def _match(rel: str, patterns: Sequence[str]) -> bool:
    """Is repo-relative POSIX path ``rel`` protected by any of ``patterns``?

    ``fnmatch`` does not treat ``/`` specially, so ``tasks/*`` protects the whole
    subtree. The single choke point both :func:`snapshot` and :func:`verify` use.
    """
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def _rel(path: Path, root: Path) -> str | None:
    """Repo-relative POSIX path, or ``None`` if ``path`` escapes ``root``.

    Path-traversal hardening: a symlink or ``..`` component that resolves outside
    the tree is refused rather than hashed.
    """
    try:
        real_root = root.resolve()
        # Resolve the parent only: resolving the entry itself would follow a
        # symlink to its target and hash foreign bytes.
        real = (path.parent.resolve() / path.name)
        return real.relative_to(real_root).as_posix()
    except (ValueError, OSError):
        return None


def _hash_file(path: Path) -> str:
    """SHA-256 of the file's bytes, streamed. Symlinks hash their target string."""
    h = hashlib.sha256()
    if path.is_symlink():
        # Never follow: hashing the target *string* makes a retargeted link show
        # up as `modified` without ever reading outside `root`.
        h.update(b"symlink:")
        h.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        return h.hexdigest()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _walk_protected(root: Path, patterns: Sequence[str]) -> dict[str, str]:
    """{relpath: sha256} for every protected file under ``root``, sorted."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = _rel(p, root)
            if rel is None or not _match(rel, patterns):
                continue
            with contextlib.suppress(OSError):
                out[rel] = _hash_file(p)
    return dict(sorted(out.items()))


@dataclass
class TamperReport:
    ok: bool
    modified: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "modified": self.modified, "added": self.added,
                "removed": self.removed, "reason": self.reason}


def snapshot(root: Path, patterns: Sequence[str]) -> dict:
    """Hash every protected file under ``root`` into a manifest dict."""
    root = Path(root)
    patterns = list(patterns)
    return {"version": VERSION, "root": str(root), "patterns": patterns,
            "files": _walk_protected(root, patterns)}


def verify(manifest: dict, root: Path) -> TamperReport:
    """Recompute the manifest against ``root`` and diff.

    ``ok=False`` means the candidate's measurement is void — discard it, do not
    record ``reward=0.0`` (see the module docstring).
    """
    root = Path(root)
    patterns = list(manifest.get("patterns") or ())
    expected = dict(manifest.get("files") or {})
    actual = _walk_protected(root, patterns)

    modified = sorted(r for r, h in actual.items() if r in expected and expected[r] != h)
    added = sorted(r for r in actual if r not in expected)
    removed = sorted(r for r in expected if r not in actual)

    if not (modified or added or removed):
        return TamperReport(True, reason=f"{len(expected)} protected file(s) unchanged")

    bits = []
    if modified:
        bits.append(f"modified {modified}")
    if added:
        bits.append(f"added {added}")
    if removed:
        bits.append(f"removed {removed}")
    return TamperReport(
        False, modified, added, removed,
        reason=("TAMPERED: protected evaluation surface changed (" + "; ".join(bits) + "). "
                "The candidate's score measures a compromised harness, not the edit — "
                "discard it as missing data (do NOT score it 0.0)."),
    )


def write_manifest(path: Path, manifest: dict) -> None:
    """Persist ``manifest`` atomically (same tmp+fsync+replace as run state)."""
    _atomic_write(Path(path), json.dumps(manifest, indent=2, sort_keys=True))


def read_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def set_readonly(root: Path, manifest: dict) -> None:
    """Best-effort defense-in-depth: clear the write bits on protected files.

    Read-modify-write of ``mode & ~0o222``, **never** an absolute ``chmod 0o444``:
    an absolute mode strips a git-tracked exec bit, which a later diff/merge check
    flags as a spurious mode change (a false-positive tamper report of our own
    making). Never raises — a filesystem that refuses chmod just doesn't get this
    extra layer; the hash manifest is the real defense.
    """
    root = Path(root)
    for rel in manifest.get("files") or {}:
        p = root / rel
        with contextlib.suppress(OSError):
            if p.is_symlink():
                continue
            mode = p.stat().st_mode & 0o7777
            p.chmod(mode & ~0o222)
