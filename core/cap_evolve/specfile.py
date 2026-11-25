"""Tiny tolerant YAML reader for the configs cap-evolve authors itself.

capevolve.yaml and meta.yaml are small, controlled documents — we don't want a YAML
dependency just to read them. Uses PyYAML if present, else a minimal reader that
handles: ``key: scalar``, ``key: [a, b]``, ``key: {a: b}``, one level of nesting under
``key:``, a block sequence of mappings (``key:\\n  - a: 1\\n    b: 2`` or
``key:\\n  - {a: 1, b: 2}`` — needed for ``objectives:``, #676), ``# comments``, and
``--- frontmatter ---`` blocks. Good enough for our schema; not a general YAML parser.
"""

from __future__ import annotations

import json as _json
import re
from pathlib import Path


def _coerce(val: str):
    s = val.strip()
    if s in ("", "[]"):
        return [] if s == "[]" else ""
    if s.startswith("[") and s.endswith("]"):
        return [_coerce(x) for x in _flow_items(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        d = {}
        for item in _flow_items(s[1:-1]):
            k, v = _flow_pair(item)
            # `{a}` and `{a: }` give a null value, as in PyYAML; `{"a": 1}` has key a
            d[_unquote_key(k)] = None if not v else _coerce(v)
        return d
    if len(s) >= 2 and (s[0], s[-1]) == ("'", "'"):
        return s[1:-1].replace("''", "'")  # '' is an escaped ' inside '...'
    if len(s) >= 2 and (s[0], s[-1]) == ('"', '"'):
        try:  # YAML's "..." escapes (\" \n \\) are JSON's for everything we write
            out = _json.loads(s, strict=False)  # strict=False: a tab inside is fine
            if isinstance(out, str):
                return out
        except ValueError:
            pass
        return s[1:-1]
    if s in ("~", "null", "Null", "NULL"):
        return None
    # YAML 1.1 booleans, exactly the forms PyYAML reads (`yEs` stays a string there too)
    if s in _YAML_TRUE:
        return True
    if s in _YAML_FALSE:
        return False
    # numbers: the same forms as PyYAML's resolver (no base-60), so `.5`, `+5`, `1_000`,
    # `0x1F`, `1.50` read as numbers; anything else (a version like `1.2.3`) stays a string
    t = s.replace("_", "")
    if _YAML_INT.match(s):
        return int(t, 10)
    if _YAML_OCT.match(s):
        return int(t, 8)
    if _YAML_HEX.match(s):
        return int(t, 16)
    if _YAML_BIN.match(s):
        return int(t, 2)
    if _YAML_FLOAT.match(s):
        return float(t)
    if _YAML_INF.match(s):
        return float("-inf") if s.startswith("-") else float("inf")
    if _YAML_NAN.match(s):
        return float("nan")
    return s


_YAML_TRUE = frozenset(("true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"))
_YAML_FALSE = frozenset(("false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"))
_YAML_INT = re.compile(r"^[-+]?(0|[1-9][0-9_]*)$")
_YAML_OCT = re.compile(r"^[-+]?0[0-7_]+$")
_YAML_HEX = re.compile(r"^[-+]?0x[0-9a-fA-F_]+$")
_YAML_BIN = re.compile(r"^[-+]?0b[01_]+$")
_YAML_FLOAT = re.compile(r"^([-+]?[0-9][0-9_]*\.[0-9_]*([eE][-+][0-9]+)?|\.[0-9_]+([eE][-+][0-9]+)?)$")
_YAML_INF = re.compile(r"^[-+]?\.(inf|Inf|INF)$")
_YAML_NAN = re.compile(r"^\.(nan|NaN|NAN)$")


def _unquote_key(k: str) -> str:
    """``"max_usd"`` / ``'max_usd'`` -> ``max_usd`` (a quoted key), else ``k`` as is."""
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        out = _coerce(k)
        return out if isinstance(out, str) else k[1:-1]
    return k


def _flow_items(inner: str) -> list[str]:
    """The items of a one-line ``[...]``/``{...}`` (the text inside the brackets), split at
    its top-level commas. Quotes count the way ``_scan_flow`` counts them: only where a
    value starts (after ``[ { , :``), so ``"a, b"`` is one item and ``don't`` is text.
    A trailing comma (``[a, b,]``) adds no item, as in PyYAML."""
    out, buf, depth, last, j = [], "", 0, ",", 0
    while j < len(inner):
        c = inner[j]
        if c in "\"'" and last in "[{,:":
            end = _scan_quoted(inner, j)
            end = len(inner) if end == -1 else end
            buf += inner[j:end]
            j, last = end, c
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(buf.strip())
            buf, last = "", ","
        else:
            buf += c
            if not c.isspace():
                last = c
        j += 1
    if buf.strip():
        out.append(buf.strip())
    return out


def _flow_pair(item: str) -> tuple[str, str | None]:
    """``(key text, value text or None)`` for one item of a ``{...}``: ``a: 1`` ->
    ``("a", "1")``, ``"a":1`` -> ``('"a"', "1")``, a bare ``a`` -> ``("a", None)``."""
    if item[:1] in ("\"", "'"):
        end = _scan_quoted(item, 0)
        if end > 0:
            rest = item[end:].lstrip()
            if not rest:
                return item[:end], None
            if rest[0] == ":":
                return item[:end], rest[1:].strip()
    m = re.search(r":(\s|$)", item)
    if m is None:
        return item, None
    return item[:m.start()].strip(), item[m.end():].strip()


def _flow_problem(s: str) -> str | None:
    """Why the built-in reader cannot read the one-line flow ``s`` (``[...]``/``{...}``)
    the way PyYAML does, or ``None`` when it can (strict mode refuses the rest)."""
    is_map = s[0] == "{"
    for item in _flow_items(s[1:-1]):
        if not item:
            return "an empty item between two commas"
        if is_map:
            k, v = _flow_pair(item)
            if k[:1] in "[{?" or k[:1] in "\"'" and _scan_quoted(k, 0) != len(k):
                return f"the key {k[:30]!r}"
            parts = [k] + ([v] if v else [])
        else:
            if (item[:1] in "\"'" and item[_scan_quoted(item, 0):].strip()
                    or item[:1] not in "\"'[{" and re.search(r":(\s|$)", item)):
                return f"a 'key: value' inside a [...] list ({item[:30]!r})"
            parts = [item]
        for part in parts:
            why = _scalar_problem(part)
            if why:
                return why
    return None


def _scalar_problem(p: str) -> str | None:
    """Why one value inside a flow ``[...]``/``{...}`` cannot be read right, or ``None``."""
    c = p[0]
    if c in "[{":
        return _flow_problem(p) if _scan_flow(p, 0) == len(p) else f"the value {p[:30]!r}"
    if c in "\"'":
        end = _scan_quoted(p, 0)
        if end != len(p):
            return f"text after a closing quote ({p[:30]!r})"
        if c == '"' and not _json_string_ok(p):
            return f"an escape in {p[:30]!r}"
        return None
    if p in ("-", "?", ":") or p[:2] in ("- ", "? ", ": ") or c in "!&*|>%@`,]}#" or c == ":":
        return f"the value {p[:30]!r}"
    if re.search(r":(\s|$)", p):
        return f"': ' inside the value {p[:30]!r}"
    return None


def _json_string_ok(s: str) -> bool:
    """``True`` when the double-quoted ``s`` decodes as JSON (the escapes ``_coerce`` reads:
    ``\\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX``)."""
    try:
        return isinstance(_json.loads(s, strict=False), str)
    except ValueError:
        return False


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


def _mark_line(e: Exception) -> tuple[int | None, str]:
    """``(1-based line, message)`` for a PyYAML error, from its marks when it has them."""
    pmark = getattr(e, "problem_mark", None)
    cmark = getattr(e, "context_mark", None)
    mark = pmark or cmark
    line = mark.line + 1 if mark is not None else None
    problem = getattr(e, "problem", None) or (str(e).splitlines() or [repr(e)])[0]
    context = getattr(e, "context", None)
    msg = f"{context}; {problem}" if context else str(problem)
    if cmark is not None and pmark is not None and cmark.line != pmark.line:
        # e.g. an unclosed quote: the error surfaces at end of file, but the
        # line the user must fix is where the quote/bracket was opened.
        msg += f" (opened at line {cmark.line + 1})"
    return line, msg


def _bad_value_line(yaml, text: str) -> int | None:
    """The 1-based line of the first value PyYAML parses but cannot build, or ``None``.

    Such errors (a ValueError for ``2024-13-01``) carry no position, so compose the
    document (no values built yet) and build each plain value on its own.
    """
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
        loader = yaml.SafeLoader("")
    except Exception:  # noqa: BLE001
        return None
    bad, todo = [], [root] if root is not None else []
    while todo:
        node = todo.pop()
        if isinstance(node, yaml.ScalarNode):
            try:
                loader.construct_object(node, deep=True)
            except Exception:  # noqa: BLE001
                bad.append(node.start_mark.line + 1)
        elif isinstance(node, yaml.SequenceNode):
            todo.extend(node.value)
        elif isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                todo.extend((k, v))
    return min(bad) if bad else None


def read_yaml(text: str, source: str | None = None, strict: bool = False) -> dict:
    """Parse ``text`` with PyYAML, or the minimal fallback reader.

    ``strict=True`` (use it for the user's ``capevolve.yaml`` spec): a YAML syntax error
    raises ``SpecError`` with the line number. ``source`` (e.g. the file path) is named in
    the message. This holds WITH OR WITHOUT PyYAML: core has no runtime dependencies, so
    without PyYAML the built-in reader runs in strict mode and raises the same
    ``SpecError`` for an unclosed quote or bracket, a tab in the indentation, a top level
    that is not a mapping, and the other cases in ``_read_yaml_minimal``'s strict checks.

    ``strict=True`` also requires the top level to be a mapping: a spec like
    ``- max_usd: 5`` or ``just a string`` is valid YAML, but every caller then does
    ``spec.get(...)`` and crashed with a traceback. An empty document gives ``{}``.

    ``strict=False`` (the default; skill ``meta.yaml`` / SKILL.md frontmatter): never
    fails. When PyYAML fails for ANY reason, fall back to the lenient minimal reader —
    several skill files carry e.g. an unquoted colon in a summary, which is not strict
    YAML but must still load.
    """
    if text.startswith("\ufeff"):
        # a UTF-8 BOM (Windows editors add one; read_text keeps it): drop it, or the
        # built-in reader names the first key "\ufeffmax_usd" and the cap is unset
        text = text[1:]
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is None:
        return _read_yaml_minimal(text, strict=strict, source=source)
    try:
        data = yaml.safe_load(text) or {}
    except Exception as e:  # noqa: BLE001
        # Not only yaml.YAMLError: PyYAML builds typed values after parsing, and a bad
        # one raises a plain error — `created: 2024-13-01` is a ValueError, `a: !!int x`
        # a ValueError, `a: !!timestamp x` an AttributeError.
        if not strict:
            return _read_yaml_minimal(text)
        if isinstance(e, yaml.YAMLError):
            line, msg = _mark_line(e)
        else:
            line, msg = _bad_value_line(yaml, text), f"cannot read this value: {e}"
        raise SpecError(msg, source=source, line=line) from e
    if strict and not isinstance(data, dict):
        raise SpecError(f"{NOT_A_MAPPING} (got {type(data).__name__}: "
                        f"{str(data)[:60]!r})", source=source, what="invalid spec")
    return data


# ---- strict checks for the built-in reader (used only when PyYAML is missing) --------

#: ``|`` / ``>`` block text, e.g. ``notes: |`` or ``notes: >-``.
_BLOCK_SCALAR = re.compile(r"^[|>][-+0-9]*$")

#: A plain value PyYAML reads as a date (and refuses when the date is not real).
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

#: Added to messages about valid YAML that the built-in reader cannot read.
_NEEDS_PYYAML = "the built-in YAML reader cannot read this; put the value on one line, or install PyYAML"


def _scan_quoted(s: str, i: int) -> int:
    """Index just past the quote that closes the quoted value opened at ``s[i]``, or -1."""
    q, j = s[i], i + 1
    while j < len(s):
        c = s[j]
        if q == '"' and c == "\\":
            j += 2
            continue
        if c == q:
            if q == "'" and s[j + 1:j + 2] == "'":  # '' is an escaped ' inside '...'
                j += 2
                continue
            return j + 1
        j += 1
    return -1


def _scan_flow(s: str, i: int) -> int:
    """Index just past the bracket that closes the ``[``/``{`` at ``s[i]``, or -1.

    Quotes count only where a value starts (after ``[ { , :``), so ``[don't]`` is fine.
    ``s`` may run over several lines (comments start at `` #``). A wrong closer
    (``[a}``) returns ``-(index + 2)`` so the caller can name it.
    """
    want, last, j = [], "", i
    while j < len(s):
        c = s[j]
        if c in "\"'" and last in "[{,:":
            end = _scan_quoted(s, j)
            if end == -1:
                return -1
            j, last = end, c
            continue
        if c == "#" and (j == 0 or s[j - 1] in " \t\n"):
            nl = s.find("\n", j)
            if nl == -1:
                return -1
            j = nl
            continue
        if c in "[{":
            want.append("]" if c == "[" else "}")
        elif c in "]}":
            if not want or c != want[-1]:
                return -(j + 2)
            want.pop()
            if not want:
                return j + 1
        if not c.isspace():
            last = c
        j += 1
    return -1


def _plain_part(v: str) -> str:
    """A plain (unquoted) value without its trailing `` # comment``."""
    m = re.search(r"(^|\s)#", v)
    return (v[:m.start()] if m else v).rstrip()


def _key_split(content: str):
    """``(key, value)`` for a ``key: value`` / ``key:`` line, else ``None``."""
    if content[:1] in ("\"", "'"):
        end = _scan_quoted(content, 0)
        if end == -1 or content[end:end + 1] != ":":
            return None
        return content[:end], content[end + 1:]
    m = re.search(r":(\s|$)", _plain_part(content))
    if m is None:
        return None
    return content[:m.start()], content[m.start() + 1:]


def _strict_value(val: str, n: int, lines: list[str], source: str | None, eof: int) -> None:
    """Raise ``SpecError`` if one value (the text after ``key:`` or ``- ``) is broken."""
    v = val.strip()
    if not v or v.startswith("#"):
        return
    c = v[0]
    if c in "\"'" or c in "[{":
        end = _scan_quoted(v, 0) if c in "\"'" else _scan_flow(v, 0)
        what = "quoted value" if c in "\"'" else ("list" if c == "[" else "mapping")
        if end < -1:
            raise SpecError(f"found {v[-end - 2]!r} that does not close the {what} "
                            f"opened here", source=source, line=n)
        if end == -1:
            # Not closed on this line. Valid YAML may continue it on the next lines, but
            # the built-in reader would misread that; an unclosed one is a plain error.
            rest = "\n".join([v] + lines[n:])
            later = _scan_quoted(rest, 0) if c in "\"'" else _scan_flow(rest, 0)
            if later > 0:
                raise SpecError(f"this {what} is not closed on its line; if it is meant "
                                f"to run over several lines, {_NEEDS_PYYAML}",
                                source=source, line=n)
            raise SpecError(f"found unexpected end of stream; the {what} is never closed "
                            f"(opened at line {n})", source=source, line=eof)
        tail = v[end:].strip()
        if tail and not tail.startswith("#"):
            raise SpecError(f"unexpected text {tail[:30]!r} after the closing "
                            f"{'quote' if c in chr(34) + chr(39) else 'bracket'}",
                            source=source, line=n)
        if c == '"' and not _json_string_ok(v[:end]):
            # YAML-only escapes (\x41 \e \0 ...) would be kept raw, and a bad one
            # ("C:\Users") is an error in PyYAML: refuse both
            raise SpecError("this double-quoted value has an escape the built-in reader "
                            "cannot read (e.g. \\x41, \\e, \\0) or an invalid one (a path "
                            "like \"C:\\Users\" needs single quotes or '\\\\'); "
                            f"{_NEEDS_PYYAML}", source=source, line=n)
        if c in "[{":
            why = _flow_problem(v[:end])
            if why:
                raise SpecError(f"cannot read this {what} ({why}); if it is valid YAML, "
                                f"{_NEEDS_PYYAML}", source=source, line=n)
        return
    if v in ("-", "?", ":") or v[:2] in ("- ", "? ", ": "):
        raise SpecError(f"a value cannot start with {v[:2].strip()!r} on this line (put list "
                        "items on their own lines under the key; a list inside a list item "
                        f"('- - a') or a '?' key needs PyYAML)", source=source, line=n)
    if c in "@`%,]}" or (c in "|>" and not _BLOCK_SCALAR.match(_plain_part(v))):
        raise SpecError(f"found character {c!r} that cannot start any token",
                        source=source, line=n)
    if c in "!&*":
        raise SpecError(f"YAML tags, anchors and aliases ({v.split()[0]!r}) are not "
                        f"supported here; {_NEEDS_PYYAML}", source=source, line=n)
    plain = _plain_part(v)
    if _DATE.match(plain):
        # PyYAML reads `2024-01-31` as a date and refuses `2024-13-01`; so must we.
        import datetime as _dt
        try:
            _dt.date(*(int(x) for x in plain.split("-")))
        except ValueError as e:
            raise SpecError(f"invalid date {plain!r}: {e} (put it in quotes if it is "
                            "not a date)", source=source, line=n) from e
    if _BLOCK_SCALAR.match(plain):
        raise SpecError(f"block text ({plain}) is not supported here; {_NEEDS_PYYAML}",
                        source=source, line=n)
    if re.search(r":(\s|$)", plain):
        raise SpecError("mapping values are not allowed here (put a value that holds "
                        "': ' in quotes)", source=source, line=n)


def _clean_value(v: str) -> str:
    """A checked value without its comment: ``"a # b"  # c`` -> ``"a # b"``."""
    v = v.strip()
    if v[:1] in ("\"", "'"):
        return v[:_scan_quoted(v, 0)]
    if v[:1] in ("[", "{"):
        return v[:_scan_flow(v, 0)]
    return _plain_part(v)


def _is_dash(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _read_yaml_minimal(text: str, strict: bool = False, source: str | None = None) -> dict:
    """The minimal reader (see ``read_yaml``).

    ``strict=False``: never fails. ``strict=True`` (only when PyYAML is missing): raise
    ``SpecError`` with the line instead of guessing, for the cases PyYAML would refuse —
    a tab in the indentation; a quote or ``[``/``{`` that is never closed; text after a
    closing quote or bracket; a top level that is a list or a plain string; a line with no
    ``key: value``; ``: `` inside an unquoted value; a line indented under a key that
    already has a value; a line whose indentation matches no open block (a bad dedent, or
    an indented first line); a ``---`` after the first key; a value that starts with
    ``@``, a backquote, ``%``, ``,``, ``]``, ``}`` or ``- ``. It also refuses
    valid YAML that this reader cannot read right (a quoted value or list over several
    lines, ``|``/``>`` block text, a flow ``{...}``/``[...]`` where a ``key: value`` line
    is expected, e.g. a one-line JSON spec, a ``key: value`` inside a flow ``[...]``, a
    list inside a list item (``- - a``), a double-quoted value with a YAML-only escape like
    ``\\x41``), and says so: reading it wrong without a word
    is the bug strict mode exists to stop. Any other error inside this reader is a
    ``SpecError`` with the line in strict mode; lenient mode keeps what it read.

    What it reads the way PyYAML does (both modes): a leading BOM is dropped; quoted keys
    are unquoted (in flow ``{...}`` too); ``key:`` with no indented child is ``None``; a
    bare ``-`` takes the mapping on the lines below it; list items may sit flush with their
    key; YAML 1.1 booleans (``yes/no/on/off``) and numbers (``.5``, ``+5``, ``1_000``,
    ``0x1F``).

    What it does NOT do like PyYAML: plain keys are not typed (``on:`` stays the string
    ``'on'``, PyYAML gives ``True``; ``1:`` stays ``'1'``), and dates (``2024-01-31``) stay
    strings. No current spec key depends on either.
    """
    data: dict = {}
    # stack entries: (indent, container, kind, col) — kind is "map" (container is a dict,
    # grown by "key: val" lines) or "seq" (container is a list, grown by "- " lines); col
    # is the column of the block's first key or dash: every line of the block starts there.
    stack = [(-1, data, "map", 0)]
    # A `key:` line with a blank value doesn't yet know whether its child block is a
    # nested mapping or a sequence — that is only decided by the NEXT line, so the
    # placeholder None written for it is held here (as (indent, parent, key)) and
    # resolved (to a dict or list, or left None) one line later. See #676: `objectives:`
    # is a block sequence of mappings, which this used to have no representation for at
    # all (every "- " line was silently dropped — ":" not in a bare "- name: reward"
    # dash line was true, but the OLD key/value split on it still mangled the result).
    pending: tuple | None = None
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    eof = text.count("\n") + 1  # the line PyYAML names for "end of stream"
    first = True
    # strict: the column where the last `key: scalar` key started — a line indented
    # past it is a continuation PyYAML refuses (or a multi-line value we cannot read)
    scalar_col: int | None = None

    def fail(msg: str, n: int, what: str = "invalid YAML") -> None:
        raise SpecError(msg, source=source, line=n, what=what)

    n = 0
    try:
        for n, raw in enumerate(lines, 1):
            pending, scalar_col, first = _minimal_line(
                n, raw, lines, eof, strict, source, stack, data, pending, scalar_col, first, fail)
    except SpecError:
        raise
    except Exception as e:  # noqa: BLE001
        # A form this reader gets wrong must never be a traceback: strict mode names the
        # line; lenient mode (never fails) keeps what it read so far.
        if strict:
            fail(f"cannot read this line ({type(e).__name__}: {e}); {_NEEDS_PYYAML}", n)
        return _close_pending(data, pending)
    return _close_pending(data, pending)


def _close_pending(data: dict, pending) -> dict:
    """A ``key:`` with no indented child is null (PyYAML: ``None``), not ``{}``."""
    if pending is not None:
        _, parent, key = pending
        parent[key] = None
    return data


def _minimal_line(n, raw, lines, eof, strict, source, stack, data, pending, scalar_col, first,
                  fail):
    """Read one line into ``stack``/``data``; returns the new (pending, scalar_col, first)."""
    keep = (pending, scalar_col, first)
    if strict:
        body = raw.strip()
        if not body or body.startswith("#"):
            return keep
        lead = raw[:len(raw) - len(raw.lstrip())]
        if "\t" in lead:
            fail("found a tab in the indentation; YAML needs spaces", n)
        marker = _plain_part(body)
        if marker == "---" or body.startswith("%"):
            # a document start (or a directive) is fine before the first key only
            if not first:
                fail("found a second document ('---' or '%' after the first key); a spec "
                     "is a single document", n)
            return keep
        if marker == "...":
            if any(x.strip() and not x.strip().startswith("#") for x in lines[n:]):
                fail("found text after the document end '...'; a spec is a single "
                     "document", n)
            return keep
        if marker.startswith("--- "):
            fail(f"a value on the '---' line is not supported here; {_NEEDS_PYYAML}", n)
        # Check the line, then read it with its comment cut the YAML way (a quote
        # only opens a value at its start, so `don't # x` is `don't`).
        if _is_dash(body):
            after = body[1:]
            rest = after.strip()
            # keep the spaces after the dash: `-   name: a` puts `name` at column 4,
            # and the item's next keys line up under it
            gap = after[:len(after) - len(after.lstrip())] or " "
            if rest in ("-", "?") or rest[:2] in ("- ", "? "):
                _strict_value(rest, n, lines, source, eof)  # refuses `- - a`, `- -`
            kv = None if rest[:1] in ("{", "[", "\"", "'") else _key_split(rest)
            if kv is not None:
                _strict_value(kv[1], n, lines, source, eof)
                clean = f"-{gap}{kv[0].strip()}: {_clean_value(kv[1]) if kv[1].strip() else ''}"
            else:
                _strict_value(rest, n, lines, source, eof)
                clean = f"-{gap}{_clean_value(rest)}" if rest else "-"
        else:
            if body[0] in "{[":
                # e.g. a one-line JSON spec: valid YAML, but this reader reads block style
                fail("a flow mapping or list ({ } or [ ]) where a 'key: value' line was "
                     "expected; write the spec in block style (one 'key: value' per line), "
                     "or install PyYAML", n)
            kv = _key_split(body)
            if kv is None:
                if first:
                    fail(f"{NOT_A_MAPPING} (got str: {_plain_part(body)[:60]!r})", n,
                         what="invalid spec")
                fail("could not find expected ':' (a 'key: value' line); if this "
                     f"continues the value above, {_NEEDS_PYYAML}", n)
            _strict_value(kv[1], n, lines, source, eof)
            clean = f"{kv[0].strip()}: {_clean_value(kv[1]) if kv[1].strip() else ''}"
        line = (lead + clean).rstrip()
    else:
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            return keep
    indent = len(line) - len(line.lstrip())
    content = line.strip()

    if strict:
        if first and _is_dash(content):
            fail(f"{NOT_A_MAPPING} (got list: {content[:60]!r})", n, what="invalid spec")
        if scalar_col is not None and indent > scalar_col and pending is None:
            fail("this line is indented under a key that already has a value; "
                 f"if it continues that value, {_NEEDS_PYYAML}", n)
    first = False

    if pending is not None:
        pend_indent, parent, key = pending
        pending = None
        if indent > pend_indent:
            is_seq = _is_dash(content)
            container = [] if is_seq else {}
            parent[key] = container
            stack.append((pend_indent, container, "seq" if is_seq else "map", indent))
        elif indent == pend_indent and _is_dash(content) and isinstance(parent, dict):
            # `caps:\n- a\n- b`: list items flush with their key (valid YAML, common).
            # The seq sits half a column left of its dashes, so the dashes do not pop it
            # but the next `key:` line at that indent does (see the loop below).
            container = []
            parent[key] = container
            stack.append((pend_indent - 0.5, container, "seq", pend_indent))
        else:
            parent[key] = None  # `key:` with no indented child is null, as in PyYAML

    while stack and (indent <= stack[-1][0]
                     or (stack[-1][0] % 1 and not _is_dash(content)
                         and indent <= stack[-1][0] + 0.5)):
        stack.pop()
    _, container, kind, col = stack[-1] if stack else (-1, data, "map", 0)
    scalar_col = None
    if strict and indent != col:
        # PyYAML refuses a line whose indent matches no open block; reading it into the
        # deeper block would move e.g. a top-level `max_usd` into `helpers:`
        if stack[-1][0] == -1 and indent and not data:
            fail("the first line is indented; start the spec at column 0", n)
        fail(f"this line's indentation (column {indent}) does not match any open block "
             f"(expected column {col})", n)

    if kind == "seq" and _is_dash(content):
        rest = content[1:].strip()
        if strict:
            kv = None if rest[:1] in ("{", "[", "\"", "'") else _key_split(rest)
        else:
            kv = rest.partition(":")[::2] if (rest and ":" in rest
                                              and rest[0] not in "{[\"'") else None
        if kv is not None:
            k, v = _unquote_key(kv[0].strip()), kv[1].strip()
            item: dict = {}
            container.append(item)
            # Siblings of `k` (more "key: val" lines of the SAME item) are
            # indented past the dash itself — same depth `k` started at.
            key_col = indent + len(content) - len(rest)
            stack.append((indent, item, "map", key_col))
            if v == "":
                item[k] = None
                # a child of `k` must be indented past `k` itself, not only past the
                # dash: `- name:\n  b: 1` is a sibling `b`, as PyYAML reads it
                pending = (key_col, item, k)
            else:
                item[k] = _coerce(v)
                scalar_col = key_col
        elif rest == "":
            # a bare `-`: its value (a mapping or list) is on the following lines
            container.append(None)
            pending = (indent, container, len(container) - 1)
        else:
            container.append(_coerce(rest))
        return pending, scalar_col, first

    if strict and _is_dash(content):
        fail("found a list item where a 'key: value' line was expected (indent list "
             "items under their key, e.g. '  - a')", n)
    if strict:
        k, v = _key_split(content)
    else:
        if ":" not in content:
            return pending, scalar_col, first
        k, _, v = content.partition(":")
    key, val = _unquote_key(k.strip()), v.strip()
    if val == "":
        container[key] = None
        pending = (indent, container, key)
    else:
        container[key] = _coerce(val)
        scalar_col = indent
    return pending, scalar_col, first


def read_frontmatter(md_path: Path) -> dict:
    txt = Path(md_path).read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    return read_yaml(txt[3:end], source=str(md_path)) if end != -1 else {}


def read_spec_file(path) -> dict:
    """Read a ``capevolve.yaml`` spec file strictly; every failure is a ``SpecError``.

    A syntax error names the file and line (``read_yaml(strict=True)``). A file that is
    not UTF-8 text, or cannot be read, is a ``SpecError`` too (``what="unreadable
    spec"``), so a script that catches ``SpecError`` gives a clean message, not a
    ``UnicodeDecodeError`` traceback.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise SpecError(f"not UTF-8 text ({e.reason}); save the spec as UTF-8",
                        source=str(path), what="unreadable spec") from e
    except OSError as e:
        raise SpecError(str(e.strerror or e), source=str(path), what="unreadable spec") from e
    return read_yaml(text, source=str(path), strict=True) or {}


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


#: (run dir, spec path, error) triples already warned about by ``spec_for_run`` in this
#: process. The run's events.jsonl is checked too (``_spec_unreadable_logged``): each
#: agent-optimize step and hook is its own process, and the run must say it once.
_SPEC_WARNED: set[tuple[str, str, str]] = set()


def _spec_unreadable_logged(run_dir, spec: str, error: str) -> bool:
    """True when the run's events.jsonl already has a ``spec_unreadable`` event for this
    spec and error. Read tolerantly: a missing file or a bad line is never an error."""
    events = getattr(run_dir, "events_path", None)
    if events is None:
        return False
    try:
        with open(events, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "spec_unreadable" not in line:
                    continue
                try:
                    ev = _json.loads(line)
                except Exception:  # noqa: BLE001 - a bad line is skipped
                    continue
                if (isinstance(ev, dict) and ev.get("kind") == "spec_unreadable"
                        and ev.get("spec") == spec and ev.get("error") == error):
                    return True
    except Exception:  # noqa: BLE001 - no log yet, or unreadable: not logged
        return False
    return False


def _warn_spec_unreadable(run_dir, path: Path, error: Exception) -> None:
    """Say once per run (stderr + a ``spec_unreadable`` event) that the run's spec has a
    syntax error and is read leniently. The step goes on; it must not go on without a
    word. A different error on the same spec is said again."""
    root = str(getattr(run_dir, "root", run_dir))
    key = (root, str(path), str(error))
    if key in _SPEC_WARNED:
        return
    _SPEC_WARNED.add(key)
    if _spec_unreadable_logged(run_dir, str(path), str(error)):
        return
    import sys as _sys
    print(f"cap-evolve: WARNING: the run's spec cannot be read strictly ({error}); this "
          "step reads it with the lenient reader instead, so the values it can read (e.g. "
          "split_mode, budget_reserve) stay as they are. Fix the spec.", file=_sys.stderr)
    log = getattr(run_dir, "log_event", None)
    if callable(log):
        try:
            log("spec_unreadable", spec=str(path), error=str(error), fallback="lenient")
        except Exception:  # noqa: BLE001 - a warning must never stop the step
            pass


def spec_for_run(run_dir, project: Path | None = None, *, warn: bool = True) -> dict:
    """The spec THIS run was started with, read from the run dir first.

    See ``resolve_spec_path`` for which file this is and why it is not simply
    ``read_yaml(project / "capevolve.yaml")``. Returns ``{}`` rather than raising when
    the resolved file is missing or unreadable, so a bad spec cannot block a budget readout.

    The entry points (``cap-evolve run``, the baseline phase, agent-optimize's host) refuse
    a spec with a syntax error before the run starts. So a syntax error here means the
    spec was edited DURING the run. Then this warns once and reads the file the old,
    lenient way: going to ``{}`` would quietly turn in-run settings (``split_mode:
    pooled``, ``budget_reserve``, ``errored_trial_policy``) back to their defaults.
    ``warn=False`` is for read-only viewers (the dashboard): they must not write events
    into a run dir or print run warnings; they show the error their own way.
    """
    path = resolve_spec_path(run_dir, project)
    if path is None:
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        return read_yaml(text, source=str(path), strict=True) or {}
    except Exception as e:  # noqa: BLE001 - SpecError, or anything else a reader raised
        if warn:
            _warn_spec_unreadable(run_dir, path, e)
        try:
            data = read_yaml(text)
        except Exception:  # noqa: BLE001
            return {}
        return data if isinstance(data, dict) else {}


# Numeric spec keys the run/estimate/doctor code reads, and the kind each must be.
_SPEC_INT_KEYS = ("max_iterations", "max_metric_calls", "num_trials", "stall", "workers",
                  "split_seed")
_SPEC_FLOAT_KEYS = ("max_usd", "max_optimizer_usd", "split_train", "split_val", "split_test")
#: Keys where a negative value is fine: any whole number is a valid ``random.Random`` seed.
_SPEC_SIGNED_KEYS = ("split_seed",)


def numeric_spec_errors(spec: dict) -> list[dict]:
    """``[{key, error, fix}]`` for numeric spec keys that are not a usable number.

    An unset key (missing or ``null``) is fine — the code uses its default. A set key must
    be a finite number, 0 or more (``split_seed`` may be negative: it is only a seed); the
    int keys must also be whole numbers. A quoted number (``max_usd: "5"``) is a string,
    not a number, and is refused too. Catching ``max_usd: five`` here means a typo in the
    spending cap fails up front with a plain message instead of a traceback (or a silent
    pass) later.
    """
    import math

    out: list[dict] = []
    for key in _SPEC_INT_KEYS + _SPEC_FLOAT_KEYS:
        val = (spec or {}).get(key)
        if val is None:
            continue
        want_int = key in _SPEC_INT_KEYS
        signed = key in _SPEC_SIGNED_KEYS
        kind = "a whole number" if want_int else "a number"
        ok = (isinstance(val, (int, float)) and not isinstance(val, bool)
              and math.isfinite(val) and (signed or val >= 0)
              and (not want_int or float(val).is_integer()))
        if not ok:
            example = "10" if want_int else "5.0"
            out.append({"key": key,
                        "error": f"{key} must be {kind}{'' if signed else ', 0 or more'} "
                                 f"(got {val!r})",
                        "fix": f"set {key} to {kind} in capevolve.yaml, e.g. {key}: {example}"})
    return out
