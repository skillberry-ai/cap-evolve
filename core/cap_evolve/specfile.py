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


# ---- model tiering --------------------------------------------------------
#
# Two tiers, because there are exactly two kinds of model call cap-evolve makes:
#
#   "proposer" — the edit proposal that DETERMINES RESULT QUALITY. Reads the
#                trajectories/reflection and writes the capability edit. Must be
#                the strong model; tiering never downgrades this path.
#   "aux"      — auxiliary/mechanical model work (summarization, reflection
#                distillation, insight synthesis, rejected-summary). Safe to run
#                on a cheaper model because its output is bookkeeping the
#                proposer reads, not the edit itself.
#
# NOTE (verified 2026-07): every auxiliary step in core today is PURE PYTHON —
# ``gepa._write_reflection`` / ``_write_focus`` / ``_build_merge``,
# ``harness._build_ledger`` / ``_build_runmap`` / ``_reconcile_journal``,
# ``skillopt._failure_patterns`` / ``_categorize`` and the whole ``diagnose``
# phase call NO model. So the aux tier costs $0 until an LLM-backed aux step
# lands (#128 insight synthesis / #129 rejected-summary); it resolves and prices
# correctly from day one so those steps can adopt it with a one-line change.
TIERS = ("proposer", "aux")

# Per-tier spec keys, most specific first. ``optimizer_model`` is the pre-existing
# single-model key and stays the proposer's source of truth, so an existing spec is
# byte-identical in behavior.
_TIER_KEYS = {
    "proposer": ("proposer_model", "optimizer_model"),
    "aux": ("aux_model", "optimizer_model"),
}


def model_for_tier(spec: dict, tier: str) -> str:
    """Resolve the model id a ``tier`` should use, from a ``capevolve.yaml`` dict.

    Falls back to ``optimizer_model`` for BOTH tiers, so a single-model spec routes
    every call site to that one model exactly as before tiering existed. Returns
    ``""`` when nothing is set (the backend picks its own default — today's
    behavior for a spec with no ``optimizer_model``).
    """
    if tier not in _TIER_KEYS:
        raise ValueError(f"unknown model tier {tier!r}; expected one of {TIERS}")
    for key in _TIER_KEYS[tier]:
        val = str((spec or {}).get(key) or "").strip()
        if val:
            return val
    return ""


def is_tiered(spec: dict) -> bool:
    """True when the spec routes the aux tier to a DIFFERENT model than the proposer.

    Used to decide whether per-tier cost accounting needs to split spend at all; a
    single-model spec keeps one undivided ``optimizer_usd`` figure as before.

    A BLANK tier counts as "different": a spec setting only ``proposer_model`` is
    tiered, because the aux tier's ``""`` resolves to the backend's own default, which
    genuinely may be a different model than the named proposer.
    """
    return model_for_tier(spec, "aux") != model_for_tier(spec, "proposer")


def read_frontmatter(md_path: Path) -> dict:
    txt = Path(md_path).read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    return read_yaml(txt[3:end]) if end != -1 else {}
