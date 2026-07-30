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
    pending: tuple[dict, str] | None = None  # (container, key) awaiting a block list
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        # Block sequences (``key:`` then ``  - item``). Without this the flow form
        # ``key: [a, b]`` parsed but the idiomatic block form silently became ``{}``,
        # so e.g. a ``protected_paths`` block list fell back to defaults with no
        # warning — a config that quietly does not apply (#142 N3).
        if stripped.startswith("- "):
            if pending is not None:
                cont, k = pending
                if not isinstance(cont.get(k), list):
                    cont[k] = []
                cont[k].append(_coerce(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        pending = None
        key, _, val = stripped.partition(":")
        key = key.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1] if stack else data
        if val.strip() == "":
            # Could be a nested mapping OR a block sequence — decide on the next line.
            container[key] = {}
            stack.append((indent, container[key]))
            pending = (container, key)
        else:
            container[key] = _coerce(val)
    return data


def read_frontmatter(md_path: Path) -> dict:
    txt = Path(md_path).read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    return read_yaml(txt[3:end]) if end != -1 else {}
