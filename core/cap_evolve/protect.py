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
import os
from pathlib import Path

from .specfile import read_yaml

MANIFEST_NAME = "protected.json"

# Default protected globs, relative to the project dir. Every entry is optional:
# a project that has no tasks.jsonl simply contributes nothing from that entry.
# ``*gold*`` is deliberately narrowed to DATA suffixes: the bare glob also caught
# prose like ``docs/golden-rules.md`` / ``GOLDEN_PATH.md``, and because
# ``protected_paths`` replaces the defaults wholesale that foot-gun could only be
# escaped by re-enumerating every default.
_DEFAULT_GLOBS = (
    "adapters", "capevolve.yaml",
    "*gold*.json", "*gold*.jsonl", "*gold*.yaml", "*gold*.yml", "*gold*.csv", "*gold*.txt",
    "**/*gold*.json", "**/*gold*.jsonl", "**/*gold*.yaml", "**/*gold*.yml",
    "**/*gold*.csv", "**/*gold*.txt",
)

# Never hashed: VCS / tool caches that are not project content.
#
# ``__pycache__`` and ``*.pyc`` are NOT on this list, deliberately. An earlier
# revision skipped them because ``check.load_adapter`` writes
# ``adapters/__pycache__/*.pyc`` during a legitimate run — but that exclusion was a
# working reward hack: a PEP 552 ``UNCHECKED_HASH`` pyc planted in the adapter's
# cache slot executes a hacked ``score()`` while ``adapter.py``'s SHA-256 stays
# byte-identical to the manifest (unchecked-hash pycs skip mtime, size AND hash
# validation, so relying on cache invalidation is no defence either). The fix is to
# stop the write, not to stop looking: ``load_adapter`` sets
# ``sys.dont_write_bytecode`` around ``exec_module``, so no ``.pyc`` appears during a
# legitimate run and bytecode is hashed like any other file. A pyc that shows up
# mid-run IS tampering, and now reads as an ``added`` protected file.
_SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
_SKIP_SUFFIXES: frozenset[str] = frozenset()


class TamperError(RuntimeError):
    """A protected (scoring / eval / task-data) file changed during the run."""


def _sha256(path: Path) -> str:
    """SHA-256 of a protected file's bytes.

    A symlink never gets hashed by following it: the bytes behind a symlink can be
    changed without touching anything inside the project dir, so following one would
    hand back a hash the guard cannot actually vouch for. Symlinks (and anything else
    that is not a regular file) get a distinct sentinel instead, which makes
    "regular file replaced by symlink" — and the reverse — a ``modified`` change.
    """
    p = Path(path)
    if p.is_symlink():
        try:
            return "symlink:" + os.readlink(p)
        except OSError as e:  # noqa: BLE001 — an unreadable link is still not a file
            return f"symlink:<unreadable {e.errno}>"
    if not p.is_file():
        return "not-a-regular-file"
    h = hashlib.sha256()
    with p.open("rb") as f:
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
    """The declared protected globs: ``protected_paths`` from the spec, else defaults.

    A ``protected_paths`` key that is present but not a list/str is a HARD error.
    Silently falling back to the defaults meant a project that declared its grader —
    and got it wrong, or hit a parser gap — believed it was protected while it was
    not. For an honesty guard, "your config did not apply" must never be silent.
    """
    cfg = Path(project_dir) / "capevolve.yaml"
    if cfg.exists():
        try:
            spec = read_yaml(cfg.read_text(encoding="utf-8")) or {}
        except Exception as e:  # noqa: BLE001 — a malformed spec must not disable the guard
            raise TamperError(
                f"cap-evolve: cannot read {cfg} to determine the protected paths "
                f"({e}). Refusing to run with an unknown protected set — fix the spec."
            ) from e
        declared = spec.get("protected_paths")
        if isinstance(declared, str):
            declared = [declared]
        if isinstance(declared, (list, tuple)):
            out = [str(x) for x in declared if str(x).strip()]
            if out:
                return out
            raise TamperError(
                f"cap-evolve: `protected_paths` in {cfg} is an EMPTY list. That would "
                "protect nothing (the scorer / eval harness / task data would all be "
                "optimizer-writable). Remove the key to use the defaults, or declare "
                "the paths."
            )
        if declared is not None:
            raise TamperError(
                f"cap-evolve: `protected_paths` in {cfg} did not parse as a list "
                f"(got {type(declared).__name__}: {declared!r}). Falling back to the "
                "defaults would silently leave a declared grader unprotected, so this "
                "is a hard error. Write it as a YAML list — either "
                "`protected_paths: [adapters, gold.json]` or a block list with `- ` "
                "items."
            )
        # Defaults + whatever data paths this spec actually names.
        extra = [str(spec[k]) for k in ("dataset_source", "split_ids_file")
                 if str(spec.get(k) or "").strip() and str(spec.get(k)) != "adapter"]
        return [*_DEFAULT_GLOBS, *extra]
    return list(_DEFAULT_GLOBS)


def resolve_protected(project_dir: Path, *, exclude: Path | None = None,
                      unprotected: list[str] | None = None) -> dict[str, Path]:
    """Expand the declared globs into ``{project-relative path -> file}``.

    Directories expand to their whole subtree. ``exclude`` (the run dir) is never
    protected — it holds the run's own mutable state. Missing entries are
    tolerated: the defaults are layout guesses, not requirements.

    Pass ``unprotected`` (a list) to collect every glob that matched nothing inside
    the project dir. Only paths under ``project_dir`` can be protected, so an
    absolute ``dataset_source`` pointing at a benchmark checkout elsewhere (a common
    swebench-style layout) contributes nothing — the caller warns about that rather
    than letting "I declared it and it wasn't protected" stay invisible.
    """
    pdir = Path(project_dir).resolve()
    ex = Path(exclude).resolve() if exclude is not None else None
    out: dict[str, Path] = {}

    def _add(p: Path) -> None:
        # Compute ``rel`` from the UN-resolved path. Resolving first followed
        # symlinks, so replacing a protected file BY a symlink pointing outside the
        # project silently dropped it from the protected set (target outside pdir →
        # ValueError → return): a free de-protection. The relative name is what the
        # manifest keys on, so it must come from the name as declared.
        try:
            rel = Path(os.path.relpath(p, pdir))
        except ValueError:
            return  # different drive (Windows) — not inside the project
        if rel.parts and rel.parts[0] == "..":
            return  # outside the project dir (a stray absolute glob) — ignore
        if _skip(rel.parts, p.name):
            return
        if ex is not None:
            try:
                p.resolve().relative_to(ex)
                return  # inside the run dir
            except (ValueError, OSError):
                pass
        # A symlink is kept in the set (``_sha256`` turns it into a sentinel hash)
        # rather than dropped: a protected path that BECOMES a symlink must read as a
        # change, not as an exemption.
        if not p.is_symlink() and not p.is_file():
            return
        out[str(rel).replace("\\", "/")] = p

    for pattern in protected_globs(pdir):
        pat = str(pattern).strip().lstrip("/")
        if not pat:
            continue
        before = len(out)
        direct = pdir / pat
        if direct.is_dir():
            for child in direct.rglob("*"):
                _add(child)
        elif direct.is_symlink() or direct.is_file():
            _add(direct)
        else:
            for hit in pdir.glob(pat):
                if hit.is_dir():
                    for child in hit.rglob("*"):
                        _add(child)
                else:
                    _add(hit)
        if unprotected is not None and len(out) == before and _looks_declared(pat):
            unprotected.append(pat)
    return out


def _looks_declared(pat: str) -> bool:
    """Is this glob an explicit declaration rather than one of our layout guesses?

    The defaults are optional by design (a project with no ``*gold*.json`` is not
    misconfigured), so only non-default patterns are worth warning about.
    """
    return pat not in _DEFAULT_GLOBS


def build_manifest(project_dir: Path, *, exclude: Path | None = None,
                   unprotected: list[str] | None = None) -> dict[str, str]:
    """``{project-relative path -> sha256}`` for every protected file, right now."""
    files = resolve_protected(project_dir, exclude=exclude, unprotected=unprotected)
    return {rel: _sha256(p) for rel, p in sorted(files.items())}


def manifest_digest(payload: dict) -> str:
    """SHA-256 of the manifest's canonical JSON — the manifest hashing itself.

    Recorded in the ``protected_manifest`` event so the manifest is covered by the
    same kind of evidence it provides for everything else. Rewriting
    ``protected.json`` to bless a tampered tree now also requires forging this digest
    in ``events.jsonl``.
    """
    canon = json.dumps({k: payload.get(k) for k in ("project_dir", "globs", "files")},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _recorded_manifest_events(run_dir) -> list[dict]:
    """Every ``protected_manifest`` event this run has logged (oldest first)."""
    out: list[dict] = []
    p = Path(run_dir.root) / "events.jsonl"
    if not p.exists():
        return out
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or "protected_manifest" not in line:
                continue
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001 — a torn line is not evidence either way
                continue
            if rec.get("kind") == "protected_manifest":
                out.append(rec)
    except OSError:
        pass
    return out


def _manifest_gone(run_dir, prior: list[dict], why: str) -> "TamperError":
    """A manifest that was recorded and is now missing/unreadable/altered is tamper.

    Re-recording from the current tree is only legitimate at FIRST creation. After
    that, the manifest's absence or corruption is itself the evidence — silently
    rebuilding it would let one optimizer step (clobber ``protected.json``, hack the
    grader) launder a tampered tree inside a single run.
    """
    run_dir.log_event("tamper_detected", context="protected manifest", changes=[
        {"path": MANIFEST_NAME, "change": "manifest_" + why,
         "expected_sha256": (prior[-1].get("digest") if prior else None)}])
    return TamperError(
        f"cap-evolve TAMPER DETECTED: this run recorded a protected-paths manifest "
        f"({len(prior)} protected_manifest event(s) in events.jsonl) but "
        f"{Path(run_dir.root) / MANIFEST_NAME} is now {why}. The manifest is the "
        "evidence that the scorer / eval harness / task data were not edited; "
        "destroying or rewriting it is itself reward hacking, so this run is aborted "
        "(the score is discarded and the test split is NOT sealed). Re-recording the "
        "hashes from the current tree would bless whatever state the tree is in now. "
        "Start a new run from a clean checkout. Full detail in events.jsonl."
    )


def ensure_manifest(run_dir, project_dir: Path | None = None) -> dict | None:
    """Record the pristine protected-file hashes, once per run (idempotent).

    Called at ``baseline`` (so the manifest is taken before any optimizer runs)
    and defensively before each optimizer invocation, which also covers a resumed
    run whose manifest predates this feature. Returns the manifest payload, or
    None when there is no project dir to protect (e.g. a bare unit test).

    Raises ``TamperError`` if this run already recorded a manifest and the file is
    now missing, unparseable, or no longer matches the digest logged with it.
    """
    pdir = Path(project_dir) if project_dir else project_dir_for(run_dir)
    if pdir is None or not Path(pdir).is_dir():
        # A project with no ``adapters/adapter.py`` gets ZERO protection. Log it once
        # so "the guard found nothing to protect" is distinguishable from "the guard
        # ran and the tree was clean" in the audit log (#142 N6).
        if not _recorded_manifest_events(run_dir) and not getattr(
                run_dir, "_protect_skip_logged", False):
            run_dir.log_event("protected_manifest_skipped", reason=(
                "no project dir with adapters/adapter.py next to the run dir — nothing "
                "is protected for this run"), project_dir=str(pdir) if pdir else None)
            try:
                run_dir._protect_skip_logged = True
            except Exception:  # noqa: BLE001 — slots/frozen run_dir: one extra line is fine
                pass
        return None
    path = Path(run_dir.root) / MANIFEST_NAME
    prior = _recorded_manifest_events(run_dir)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            if prior:
                raise _manifest_gone(run_dir, prior, "unparseable") from None
            payload = None  # first creation raced/torn: recording it now is honest
        else:
            want = prior[-1].get("digest") if prior else None
            if want and manifest_digest(payload) != want:
                raise _manifest_gone(run_dir, prior, "altered")
            return payload
    elif prior:
        raise _manifest_gone(run_dir, prior, "missing")

    unprotected: list[str] = []
    payload = {"project_dir": str(Path(pdir).resolve()),
               "globs": protected_globs(Path(pdir)),
               "files": build_manifest(pdir, exclude=Path(run_dir.root),
                                       unprotected=unprotected)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    run_dir.log_event("protected_manifest", n_files=len(payload["files"]),
                      globs=payload["globs"], digest=manifest_digest(payload))
    if unprotected:
        # Only paths INSIDE the project dir can be protected. A declared glob that
        # matched nothing there (typically ground truth in a benchmark checkout
        # referenced by absolute path) is silently unguarded — say so (#142 N7).
        run_dir.log_event("protected_paths_unmatched", globs=unprotected, reason=(
            "declared protected path(s) matched no file inside the project dir, so "
            "they are NOT covered by the tamper manifest — only paths under "
            f"{Path(pdir).resolve()} can be hashed"))
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
        named += f"; (+{len(changes) - 8} more — full list in events.jsonl)"
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
    """Would ``path`` be protected for ``project_dir``? (used by the honesty hook).

    Path comparison is case-folded. On a case-insensitive filesystem (APFS/NTFS
    default) ``Adapters/adapter.py`` is the SAME inode as the protected
    ``adapters/adapter.py``, so a case-varied spelling used to slip past the hook
    untouched (#142 N2) — and ``os.path.normcase`` does not help, it is a no-op on
    POSIX including macOS. Folding unconditionally can only over-block, and only for a
    genuinely distinct file whose name differs from a protected one by case alone; for
    an honesty guard that is the right direction to err.
    """
    pdir = Path(project_dir).resolve()
    p = Path(path)
    # Resolve the PARENT, keep the final component as named — same reason as ``_add``:
    # fully resolving follows a symlink out of the project dir, so a protected path that
    # is (or is replaced by) a symlink answered False and the hook allowed the write.
    try:
        p = p.parent.resolve() / p.name
        rel = str(Path(os.path.relpath(p, pdir))).replace("\\", "/")
    except (ValueError, OSError):
        return False
    if rel == ".." or rel.startswith("../"):
        return False
    if _skip(Path(rel).parts, Path(rel).name):
        return False
    nrel, nname = rel.lower(), Path(rel).name.lower()
    for pattern in protected_globs(pdir):
        pat = str(pattern).strip().lstrip("/").lower()
        if not pat:
            continue
        if nrel == pat or nrel.startswith(pat.rstrip("/") + "/"):
            return True
        if fnmatch.fnmatch(nrel, pat) or fnmatch.fnmatch(nname, pat):
            return True
    return False
