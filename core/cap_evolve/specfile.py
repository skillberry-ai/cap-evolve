"""Tiny tolerant YAML reader for the configs cap-evolve authors itself.

capevolve.yaml and meta.yaml are small, controlled documents — we don't want a YAML
dependency just to read them. Uses PyYAML if present, else a minimal reader that
handles: ``key: scalar``, ``key: [a, b]``, ``key: {a: b}``, one level of nesting under
``key:``, a block sequence of mappings (``key:\\n  - a: 1\\n    b: 2`` or
``key:\\n  - {a: 1, b: 2}`` — needed for ``objectives:``, #676), ``# comments``, and
``--- frontmatter ---`` blocks. Good enough for our schema; not a general YAML parser.
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
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        if not inner:
            return {}
        d = {}
        for pair in _split_list(inner):
            k, _, v = pair.partition(":")
            d[k.strip()] = _coerce(v.strip())
        return d
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


class SpecError(ValueError):
    """A YAML document (e.g. ``capevolve.yaml``) has a syntax error.

    Raised instead of quietly falling back to the minimal reader: that reader never
    fails, so a broken spec (unclosed quote/bracket, a tab) used to turn into WRONG
    values — e.g. ``max_usd: "5`` read as the string ``'"5'`` — and every check said ok.
    ``line`` is 1-based, or ``None`` when PyYAML did not report a position.
    """

    def __init__(self, message: str, *, source: str | None = None, line: int | None = None,
                 what: str = "invalid YAML"):
        self.source = source
        self.line = line
        where = f" in {source}" if source else ""
        if line is not None:
            where = f"{where}, line {line}" if where else f" at line {line}"
        super().__init__(f"{what}{where}: {message}")


#: Message for a spec that parses but whose top level is a list/string/number.
NOT_A_MAPPING = "capevolve.yaml must be a mapping of keys and values"


def read_yaml(text: str, source: str | None = None, strict: bool = False) -> dict:
    """Parse ``text`` with PyYAML, or the minimal fallback reader.

    ``strict=True`` (use it for the user's ``capevolve.yaml`` spec): a YAML syntax error
    raises ``SpecError`` with the line number, and the fallback reader is used ONLY when
    PyYAML is not installed. ``source`` (e.g. the file path) is named in the message.

    ``strict=True`` also requires the top level to be a mapping: a spec like
    ``- max_usd: 5`` or ``just a string`` is valid YAML, but every caller then does
    ``spec.get(...)`` and crashed with a traceback. An empty document gives ``{}``.

    ``strict=False`` (the default; skill ``meta.yaml`` / SKILL.md frontmatter): when
    PyYAML fails, fall back to the lenient minimal reader — several skill files carry
    e.g. an unquoted colon in a summary, which is not strict YAML but must still load.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            if not strict:
                return _read_yaml_minimal(text)
            pmark = getattr(e, "problem_mark", None)
            cmark = getattr(e, "context_mark", None)
            mark = pmark or cmark
            line = mark.line + 1 if mark is not None else None
            problem = getattr(e, "problem", None) or str(e).splitlines()[0]
            context = getattr(e, "context", None)
            msg = f"{context}; {problem}" if context else str(problem)
            if cmark is not None and pmark is not None and cmark.line != pmark.line:
                # e.g. an unclosed quote: the error surfaces at end of file, but the
                # line the user must fix is where the quote/bracket was opened.
                msg += f" (opened at line {cmark.line + 1})"
            raise SpecError(msg, source=source, line=line) from e
        if strict and not isinstance(data, dict):
            raise SpecError(f"{NOT_A_MAPPING} (got {type(data).__name__}: "
                            f"{str(data)[:60]!r})", source=source, what="invalid spec")
        return data
    return _read_yaml_minimal(text)


def _read_yaml_minimal(text: str) -> dict:
    """The minimal, never-failing reader (see ``read_yaml``)."""
    data: dict = {}
    # stack entries: (indent, container, kind) — kind is "map" (container is a dict,
    # grown by "key: val" lines) or "seq" (container is a list, grown by "- " lines).
    stack = [(-1, data, "map")]
    # A `key:` line with a blank value doesn't yet know whether its child block is a
    # nested mapping or a sequence — that is only decided by the NEXT line, so the
    # placeholder {} written for it is held here (as (indent, parent, key)) and
    # resolved (possibly replaced with a list) one line later. See #676: `objectives:`
    # is a block sequence of mappings, which this used to have no representation for at
    # all (every "- " line was silently dropped — ":" not in a bare "- name: reward"
    # dash line was true, but the OLD key/value split on it still mangled the result).
    pending: tuple | None = None
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        content = line.strip()

        if pending is not None:
            pend_indent, parent, key = pending
            pending = None
            if indent > pend_indent:
                is_seq = content.startswith("- ") or content == "-"
                container = [] if is_seq else {}
                parent[key] = container
                stack.append((pend_indent, container, "seq" if is_seq else "map"))

        while stack and indent <= stack[-1][0]:
            stack.pop()
        _, container, kind = stack[-1] if stack else (-1, data, "map")

        if kind == "seq" and (content.startswith("- ") or content == "-"):
            rest = content[1:].strip()
            if rest and ":" in rest and rest[0] not in "{[\"'":
                k, _, v = rest.partition(":")
                k, v = k.strip(), v.strip()
                item: dict = {}
                container.append(item)
                # Siblings of `k` (more "key: val" lines of the SAME item) are
                # indented past the dash itself — same depth `k` started at.
                stack.append((indent, item, "map"))
                if v == "":
                    item[k] = {}
                    pending = (indent, item, k)
                else:
                    item[k] = _coerce(v)
            else:
                container.append(_coerce(rest))
            continue

        if ":" not in content:
            continue
        key, _, val = content.partition(":")
        key, val = key.strip(), val.strip()
        if val == "":
            container[key] = {}
            pending = (indent, container, key)
        else:
            container[key] = _coerce(val)
    return data


def read_frontmatter(md_path: Path) -> dict:
    txt = Path(md_path).read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    return read_yaml(txt[3:end], source=str(md_path)) if end != -1 else {}


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


def resolve_spec_path(run_dir, project: Path | None = None) -> Path | None:
    """The spec file THIS run was actually started with, or ``None``.

    ``cap-evolve run --spec`` fully supports a non-default spec filename, and every
    agent-mode run of a variant spec (``capevolve.agentopt.yaml``) hit the same silent
    failure elsewhere — readers guessed ``capevolve.yaml``, found a *different* spec (or
    none), and silently read the wrong (or no) config. ``cli._resolve_spec`` already logs
    the resolved path into the run dir as the ``run_config`` event's ``spec`` field
    precisely so a finished run is self-describing. Read that; fall back to
    ``project/capevolve.yaml`` only when it is absent (an older run dir, or no
    ``run_config`` event at all).
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
                # ``spec_resolved`` is logged by the baseline phase the moment the run dir exists, BEFORE
                # cli.py logs ``run_config`` (which comes after the baseline): config that decides how the
                # baseline itself runs (split_mode) must already resolve to the run's spec.
                if ev.get("kind") in ("run_config", "spec_resolved") and ev.get("spec"):
                    candidates.append(Path(str(ev["spec"])))
                    break
    except Exception:  # noqa: BLE001
        pass
    if project:
        candidates.append(Path(project) / "capevolve.yaml")
    for p in candidates:
        if p.is_file():
            return p
    return None


def spec_for_run(run_dir, project: Path | None = None) -> dict:
    """The spec THIS run was started with, read from the run dir first.

    See ``resolve_spec_path`` for which file this is and why it is not simply
    ``read_yaml(project / "capevolve.yaml")``. Returns ``{}`` rather than raising when
    the resolved file is missing/malformed, so a bad spec cannot block a budget readout.
    """
    path = resolve_spec_path(run_dir, project)
    if path is None:
        return {}
    try:
        return read_yaml(path.read_text(encoding="utf-8"), strict=True) or {}
    except Exception:  # noqa: BLE001
        return {}


# Numeric spec keys the run/estimate/doctor code reads, and the kind each must be.
_SPEC_INT_KEYS = ("max_iterations", "max_metric_calls", "num_trials", "stall", "workers",
                  "split_seed")
_SPEC_FLOAT_KEYS = ("max_usd", "max_optimizer_usd", "split_train", "split_val", "split_test")


def numeric_spec_errors(spec: dict) -> list[dict]:
    """``[{key, error, fix}]`` for numeric spec keys that are not a usable number.

    An unset key (missing or ``null``) is fine — the code uses its default. A set key must
    be a finite, non-negative number; the int keys must also be whole numbers. Catching
    ``max_usd: five`` here means a typo in the spending cap fails up front with a plain
    message instead of a traceback (or a silent pass) later.
    """
    import math

    out: list[dict] = []
    for key in _SPEC_INT_KEYS + _SPEC_FLOAT_KEYS:
        val = (spec or {}).get(key)
        if val is None:
            continue
        want_int = key in _SPEC_INT_KEYS
        kind = "a whole number" if want_int else "a number"
        ok = (isinstance(val, (int, float)) and not isinstance(val, bool)
              and math.isfinite(val) and val >= 0
              and (not want_int or float(val).is_integer()))
        if not ok:
            example = "10" if want_int else "5.0"
            out.append({"key": key,
                        "error": f"{key} must be {kind}, 0 or more (got {val!r})",
                        "fix": f"set {key} to {kind} in capevolve.yaml, e.g. {key}: {example}"})
    return out
