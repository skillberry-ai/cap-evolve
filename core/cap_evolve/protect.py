"""Protected-paths tamper guard — proof the optimizer never edited the grader.

cap-evolve already makes the *evaluation* honest (seeded splits, a sealed test
split, a val-only significance gate). But when the capability under optimization
is tool code or a skill package, the optimizer is a coding agent with write tools
running next to the project — nothing structural stopped it from editing the
**scorer / eval harness / task data** instead of the target. A candidate that
"improves" by rewriting ``score()`` is reward hacking, and every number after it
is fiction.

This module makes "only edit the target, never the grader" a *structural*
guarantee, the same posture the test seal already has:

  1. ``ensure_manifest`` records a SHA-256 of every protected file at the START of
     a run (``baseline``), persisted as ``protected.json`` in the run dir.
  2. ``verify`` re-hashes them after every optimizer invocation and again before
     ``finalize`` burns the seal. Any change / deletion / newly-added protected
     file logs a ``tamper_detected`` event and raises ``TamperError``, naming the
     file — the run aborts, so the candidate cannot advance and the test split
     cannot be sealed on a tampered grader.

Why a content hash: mtime is trivially spoofable (``os.utime``) and a size check
misses same-length edits. SHA-256 over the bytes is the only claim we can make
honestly — and ``hashlib`` is stdlib, so this costs zero dependencies.

What counts as protected (defaults, derived from the project layout):
  * ``adapters/`` — ``tasks()`` / ``run_target()`` / ``score()`` live here: the
    ground truth and the grader;
  * ``capevolve.yaml`` — declares splits, ratios, gate mode/k, budget;
  * the ``dataset_source`` and ``split_ids_file`` the spec names (task data + the
    frozen partition), when they resolve to real paths;
  * anything matching ``*gold*`` in the project dir (answer keys).
The seed capability dir is deliberately NOT protected — it is the target.

Override with a ``protected_paths`` list in ``capevolve.yaml`` (project-relative
paths, dirs, or glob patterns). That replaces the defaults entirely, so a project
whose grader lives elsewhere can declare it.

Pure stdlib (hashlib + json).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path

from .specfile import read_yaml

MANIFEST_NAME = "protected.json"

# Default protected globs, relative to the project dir. Every entry is optional:
# a project that has no tasks.jsonl simply contributes nothing from that entry.
_DEFAULT_GLOBS = ("adapters", "capevolve.yaml", "*gold*", "**/*gold*")

# Never hashed: caches/vcs churn that is not content. ``__pycache__`` matters a
# lot — ``check.load_adapter`` execs ``adapters/adapter.py``, and importing a
# sibling helper writes ``adapters/__pycache__/*.pyc`` DURING a legitimate run.
# Hashing those would flag every normal run as tampering (a guard that blocks
# normal runs is worse than no guard).
_SKIP_DIRS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


class TamperError(RuntimeError):
    """A protected (scoring / eval / task-data) file changed during the run."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _skip(rel_parts: tuple[str, ...], name: str) -> bool:
    return (any(p in _SKIP_DIRS for p in rel_parts)
            or Path(name).suffix in _SKIP_SUFFIXES)


def project_dir_for(run_dir) -> Path | None:
    """The ``.capevolve/project`` sibling of a run dir, or None.

    Lets the guard run in ``gepa``/``skillopt``, which don't thread a
    ``project_dir`` — the layout is fixed (``.capevolve/run_<ts>`` next to
    ``.capevolve/project``), so no new plumbing is needed to find the grader.
    """
    proj = Path(run_dir.root).parent / "project"
    return proj if (proj / "adapters" / "adapter.py").exists() else None


def protected_globs(project_dir: Path) -> list[str]:
    """The declared protected globs: ``protected_paths`` from the spec, else defaults."""
    cfg = Path(project_dir) / "capevolve.yaml"
    if cfg.exists():
        try:
            spec = read_yaml(cfg.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — a malformed spec must not disable the guard
            spec = {}
        declared = spec.get("protected_paths")
        if isinstance(declared, str):
            declared = [declared]
        if declared:
            return [str(x) for x in declared if str(x).strip()]
        # Defaults + whatever data paths this spec actually names.
        extra = [str(spec[k]) for k in ("dataset_source", "split_ids_file")
                 if str(spec.get(k) or "").strip() and str(spec.get(k)) != "adapter"]
        return [*_DEFAULT_GLOBS, *extra]
    return list(_DEFAULT_GLOBS)


def resolve_protected(project_dir: Path, *, exclude: Path | None = None) -> dict[str, Path]:
    """Expand the declared globs into ``{project-relative path -> file}``.

    Directories expand to their whole subtree. ``exclude`` (the run dir) is never
    protected — it holds the run's own mutable state. Missing entries are
    tolerated: the defaults are layout guesses, not requirements.
    """
    pdir = Path(project_dir).resolve()
    ex = Path(exclude).resolve() if exclude is not None else None
    out: dict[str, Path] = {}

    def _add(p: Path) -> None:
        if not p.is_file():
            return
        try:
            rel = p.resolve().relative_to(pdir)
        except ValueError:
            return  # outside the project dir (a stray absolute glob) — ignore
        if ex is not None:
            try:
                p.resolve().relative_to(ex)
                return  # inside the run dir
            except ValueError:
                pass
        if _skip(rel.parts, p.name):
            return
        out[str(rel).replace("\\", "/")] = p

    for pattern in protected_globs(pdir):
        pat = str(pattern).strip().lstrip("/")
        if not pat:
            continue
        direct = pdir / pat
        if direct.is_dir():
            for child in direct.rglob("*"):
                _add(child)
            continue
        if direct.is_file():
            _add(direct)
            continue
        for hit in pdir.glob(pat):
            if hit.is_dir():
                for child in hit.rglob("*"):
                    _add(child)
            else:
                _add(hit)
    return out


def build_manifest(project_dir: Path, *, exclude: Path | None = None) -> dict[str, str]:
    """``{project-relative path -> sha256}`` for every protected file, right now."""
    files = resolve_protected(project_dir, exclude=exclude)
    return {rel: _sha256(p) for rel, p in sorted(files.items())}


def ensure_manifest(run_dir, project_dir: Path | None = None) -> dict | None:
    """Record the pristine protected-file hashes, once per run (idempotent).

    Called at ``baseline`` (so the manifest is taken before any optimizer runs)
    and defensively before each optimizer invocation, which also covers a resumed
    run whose manifest predates this feature. Returns the manifest payload, or
    None when there is no project dir to protect (e.g. a bare unit test).
    """
    pdir = Path(project_dir) if project_dir else project_dir_for(run_dir)
    if pdir is None or not Path(pdir).is_dir():
        return None
    path = Path(run_dir.root) / MANIFEST_NAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — torn manifest: re-record rather than crash
            pass
    payload = {"project_dir": str(Path(pdir).resolve()),
               "globs": protected_globs(Path(pdir)),
               "files": build_manifest(pdir, exclude=Path(run_dir.root))}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    run_dir.log_event("protected_manifest", n_files=len(payload["files"]),
                      globs=payload["globs"])
    return payload


def diff_manifest(recorded: dict[str, str], current: dict[str, str]) -> list[dict]:
    """Every difference between a recorded and a current manifest."""
    out: list[dict] = []
    for rel, want in sorted(recorded.items()):
        got = current.get(rel)
        if got is None:
            out.append({"path": rel, "change": "deleted", "expected_sha256": want})
        elif got != want:
            out.append({"path": rel, "change": "modified",
                        "expected_sha256": want, "actual_sha256": got})
    for rel in sorted(set(current) - set(recorded)):
        out.append({"path": rel, "change": "added", "actual_sha256": current[rel]})
    return out


def verify(run_dir, project_dir: Path | None = None, *, context: str = "") -> list[dict]:
    """Re-hash the protected files; raise ``TamperError`` on ANY difference.

    Returns ``[]`` when clean (or when there is nothing to protect). On a
    mismatch a ``tamper_detected`` event is logged BEFORE raising, so the audit
    log records the tamper even though the run aborts. We deliberately do not
    "repair" the file — the evidence stays on disk for the human to inspect.
    """
    recorded = ensure_manifest(run_dir, project_dir)
    if not recorded:
        return []
    pdir = Path(recorded.get("project_dir") or (project_dir or ""))
    if not pdir.is_dir():
        return []
    current = build_manifest(pdir, exclude=Path(run_dir.root))
    changes = diff_manifest(recorded.get("files") or {}, current)
    if not changes:
        return []
    run_dir.log_event("tamper_detected", context=context, changes=changes,
                      project_dir=str(pdir))
    named = "; ".join(f"{c['change']} {c['path']}" for c in changes[:8])
    if len(changes) > 8:
        named += f"; (+{len(changes) - 8} more)"
    raise TamperError(
        f"cap-evolve TAMPER DETECTED{f' during {context}' if context else ''}: "
        f"{len(changes)} protected file(s) changed under {pdir} — {named}. "
        "Protected paths are the scorer / eval harness / task data; a candidate that "
        "edits them is reward hacking, so this run is aborted (the score is discarded "
        "and the test split is NOT sealed). Optimize the capability, not the grader. "
        f"Recorded hashes: {Path(run_dir.root) / MANIFEST_NAME}. "
        "If a path is legitimately editable, remove it from `protected_paths` in "
        "capevolve.yaml and start a new run."
    )


def is_protected(project_dir: Path, path: Path) -> bool:
    """Would ``path`` be protected for ``project_dir``? (used by the honesty hook)."""
    pdir = Path(project_dir).resolve()
    try:
        rel = str(Path(path).resolve().relative_to(pdir)).replace("\\", "/")
    except ValueError:
        return False
    if _skip(Path(rel).parts, Path(rel).name):
        return False
    for pattern in protected_globs(pdir):
        pat = str(pattern).strip().lstrip("/")
        if not pat:
            continue
        if rel == pat or rel.startswith(pat.rstrip("/") + "/"):
            return True
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(Path(rel).name, pat):
            return True
    return False
