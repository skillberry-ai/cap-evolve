"""Tiny tolerant YAML reader for the configs cap-evolve authors itself.

capevolve.yaml and meta.yaml are small, controlled documents — we don't want a YAML
dependency just to read them. Uses PyYAML if present, else a minimal reader that
handles: ``key: scalar``, ``key: [a, b]``, one level of nesting under ``key:``,
``# comments``, and ``--- frontmatter ---`` blocks. Good enough for our schema;
not a general YAML parser.
"""

from __future__ import annotations

from pathlib import Path


def _coerce(val: str):
    s = val.strip()
    if s in ("", "[]"):
        return [] if s == "[]" else ""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_coerce(x) for x in _split_list(inner)] if inner else []
    if (s[0], s[-1]) in (('"', '"'), ("'", "'")):
        return s[1:-1]
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    # exact round-trip only, so "007"/"1_000"/versions stay strings
    try:
        if str(int(s)) == s:
            return int(s)
    except ValueError:
        pass
    try:
        if str(float(s)) == s:
            return float(s)
    except ValueError:
        pass
    return s


def _split_list(inner: str) -> list[str]:
    out, buf, depth = [], "", 0
    for ch in inner:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


def _strip_comment(line: str) -> str:
    out, in_s, q = "", False, ""
    for ch in line:
        if in_s:
            out += ch
            if ch == q:
                in_s = False
        elif ch in "\"'":
            in_s, q = True, ch; out += ch
        elif ch == "#":
            break
        else:
            out += ch
    return out


def read_yaml(text: str) -> dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        pass
    data: dict = {}
    stack = [(-1, data)]  # (indent, container)
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip() or ":" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        key = key.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1] if stack else data
        if val.strip() == "":
            container[key] = {}
            stack.append((indent, container[key]))
        else:
            container[key] = _coerce(val)
    return data


def read_frontmatter(md_path: Path) -> dict:
    txt = Path(md_path).read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    return read_yaml(txt[3:end]) if end != -1 else {}


def resolve_project_path(project, value) -> Path:
    """Resolve a spec path key against the PROJECT dir — the one rule, for every reader.

    A relative path in ``capevolve.yaml`` means "relative to the project dir that
    contains the spec". Absolute paths are returned unchanged.

    This exists because it used to be resolved twice, differently: ``cap-evolve check``
    (``pipeline_selftest``) resolved project-relative and reported a missing file, while
    ``cap-evolve run`` probed the caller's *cwd* first. The same key therefore named a
    different file depending on where ``run`` was invoked from, and on a miss ``run``
    dropped the flag without a word — so the optimizer silently received cap-evolve's
    generic template instead of the capability-scoped instructions intake authored (#252).
    """
    v = Path(str(value))
    return v if v.is_absolute() else Path(project) / v


#: Where a project's optimizer-instructions template lives when the spec does not name one.
DEFAULT_INSTRUCTIONS_REL = "optimizer/INSTRUCTIONS.md"


def resolve_instructions_file(spec: dict, project) -> tuple[Path, bool, str]:
    """Resolve ``optimizer_instructions_file`` — ONE rule, for every consumer.

    Returns ``(path, exists, warning)``. ``warning`` is non-empty only when the spec
    NAMED a file that is not there: falling back then means the optimizer reads
    cap-evolve's generic template instead of the capability-scoped one, and a step that
    did not get what it needed must not look like a step that had nothing to propose
    (#252). An absent default path is normal and silent.

    Shared because it was resolved in two places — ``cli.py`` for the deterministic
    algorithms, and an agent-mode host — and the second copy also had to re-derive the
    default and the warning text. Two copies of a resolution rule is exactly how #252
    happened the first time.
    """
    named = str(spec.get("optimizer_instructions_file") or "").strip()
    path = resolve_project_path(project, named or DEFAULT_INSTRUCTIONS_REL)
    if path.exists():
        return path, True, ""
    warning = ""
    if named:
        warning = (f"optimizer_instructions_file {named!r} does not exist (resolved "
                   f"project-relative to {path}) — the optimizer will get cap-evolve's "
                   f"GENERIC template, not your capability-scoped one; `cap-evolve check` "
                   f"and the implement-and-check self-test catch this")
    return path, False, warning


def spec_for_run(run_dir, project: Path | None = None) -> dict:
    """The spec THIS run was started with, read from the run dir first.

    Why this is not ``read_yaml(project / "capevolve.yaml")``: ``cap-evolve run --spec``
    fully supports a non-default spec filename, and every agent-mode run of a variant
    spec (``capevolve.agentopt.yaml``) hit the same silent failure — the readout scripts
    guessed ``capevolve.yaml``, found a *different* spec (or none), and reported
    ``predicates: []``. The entire re-read-your-constraints discipline then no-ops
    without a word: an agent asks "may I spend?", is told there are no constraints, and
    keeps going past a ceiling the spec did define.

    ``cli._resolve_spec`` already logs the resolved path into the run dir as the
    ``run_config`` event's ``spec`` field precisely so a finished run is self-describing.
    Read that; fall back to ``project/capevolve.yaml`` only when it is absent (an older
    run dir), and return ``{}`` rather than raising, so a malformed spec cannot block a
    budget readout.
    """
    import json as _json

    candidates: list[Path] = []
    try:
        with Path(run_dir.events_path).open(encoding="utf-8") as f:
            for line in f:
                try:
                    ev = _json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if ev.get("kind") == "run_config" and ev.get("spec"):
                    candidates.append(Path(str(ev["spec"])))
                    break
    except Exception:  # noqa: BLE001
        pass
    if project:
        candidates.append(Path(project) / "capevolve.yaml")
    for p in candidates:
        if p.is_file():
            try:
                return read_yaml(p.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001
                return {}
    return {}
