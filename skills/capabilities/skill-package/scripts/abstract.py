"""skill-package capability — optimize an Agent Skill package (SKILL.md + refs + scripts).

A skill package is a directory: a required ``SKILL.md`` (YAML frontmatter
``name``/``description`` + a Markdown body) plus optional ``references/`` (docs
loaded on demand), ``scripts/`` (executables), and ``assets/``. Optimizing a skill
means editing that text to improve how a downstream agent uses it.

``validate`` here encodes the skill-creator / Agent-Skills authoring rules so the
optimizer can't drift into an invalid package (all rules sourced to first-party
Anthropic docs — see references/concepts.md):
  - frontmatter has ``name`` (<=64 chars, [a-z0-9-], no "anthropic"/"claude",
    no XML tags) and a non-empty ``description`` (<=1024 chars, no XML tags) that
    says WHAT + WHEN ("use when").
  - SKILL.md body stays under ~500 lines AND ~5k tokens (progressive disclosure
    budget; the body is a recurring per-session token cost).
  - references are one level deep and any long reference (>300 lines) has a TOC.
  - referenced files that the body points at actually exist.

Soft authoring lints (warnings, not failures): a first-person description
(point-of-view drift hurts discovery), all-caps CRITICAL/ALWAYS/MUST/NEVER in the
description (over-triggers current models), and a long description that risks the
1,536-char listing truncation (description + when_to_use) — front-load the use case.

Edit ops (mirrored by the mock optimizer): {"file","op":"set|append|ensure_contains","text"}.
"""

from __future__ import annotations

import re
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)
XML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")  # an actual tag, not a stray "<"
MAX_BODY_LINES = 500
MAX_BODY_TOKENS = 5000            # ~chars/4; Level-2 body budget
CHARS_PER_TOKEN = 4
LONG_REF_LINES = 300
LISTING_CAP_CHARS = 1536          # description + when_to_use truncation in the listing
LONG_DESC_CHARS = 1024            # hard cap; also the front-load advisory threshold


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    body = text[m.end():]
    return fm, body


def _subpackages(capability_dir: Path) -> list[Path]:
    """Immediate sub-directories that are themselves skill packages (contain SKILL.md).

    A capability_path may hold ONE skill (SKILL.md at the top) or SEVERAL shared
    skills as immediate sub-packages (e.g. seed_capability/{docx,pptx,xlsx,pdf}/).
    Returns the sub-package dirs (sorted) when this is a MULTI-skill root, else []."""
    # A missing/typoed/non-dir path is NOT a multi-skill root — return [] so the caller
    # falls through to the single-skill path and reports a clean validation error
    # ("no SKILL.md") instead of raising FileNotFoundError on iterdir().
    if not capability_dir.is_dir() or (capability_dir / "SKILL.md").exists():
        return []
    return sorted(
        sub for sub in capability_dir.iterdir()
        if sub.is_dir() and (sub / "SKILL.md").exists()
    )


def _materialize_one(skill_dir: Path, prefix: str = "") -> dict:
    """Flatten ONE skill package's SKILL.md + references into named components."""
    parts = {}
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        parts[f"{prefix}SKILL.md"] = skill_md.read_text(encoding="utf-8")
    refs = skill_dir / "references"
    if refs.is_dir():
        for f in sorted(refs.glob("*.md")):
            parts[f"{prefix}references/{f.name}"] = f.read_text(encoding="utf-8")
    return parts


def materialize(capability_dir: Path) -> dict:
    """Flatten SKILL.md + references into named text components.

    Supports BOTH a single-skill capability_path (SKILL.md at the top) and a
    MULTI-skill root holding several immediate sub-packages: components from each
    sub-package are namespaced by ``<skill>/`` (e.g. ``docx/SKILL.md``,
    ``pdf/references/forms.md``)."""
    capability_dir = Path(capability_dir)
    subs = _subpackages(capability_dir)
    if subs:
        parts: dict = {}
        for sub in subs:
            parts.update(_materialize_one(sub, prefix=f"{sub.name}/"))
        return parts
    return _materialize_one(capability_dir)


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    capability_dir = Path(capability_dir)
    report = {"changed": []}
    for e in edits or []:
        target = capability_dir / e["file"]
        op = e.get("op", "set")
        text = e.get("text", "")
        target.parent.mkdir(parents=True, exist_ok=True)
        cur = target.read_text(encoding="utf-8") if target.exists() else ""
        if op == "set":
            new = text
        elif op == "append":
            new = cur + text
        elif op == "ensure_contains":
            new = cur if (text.strip() and text.strip() in cur) else cur + text
        else:
            raise ValueError(f"unknown op {op!r}")
        if new != cur:
            target.write_text(new, encoding="utf-8")
            report["changed"].append(e["file"])
    return report


def validate(capability_dir: Path) -> dict:
    """Enforce the Agent-Skills authoring rules. Returns {ok, problems, warnings}.

    For a MULTI-skill root (several immediate sub-packages), validate EACH
    sub-package and aggregate: problems/warnings are namespaced by ``<skill>:`` and
    ``ok`` is True only if every sub-package is valid."""
    capability_dir = Path(capability_dir)
    subs = _subpackages(capability_dir)
    if subs:
        problems: list[str] = []
        warnings: list[str] = []
        names: list[str] = []
        for sub in subs:
            v = _validate_one(sub)
            names.append(v.get("name", sub.name))
            problems += [f"{sub.name}: {p}" for p in v["problems"]]
            warnings += [f"{sub.name}: {w}" for w in v["warnings"]]
        return {"ok": not problems, "name": ",".join(names),
                "problems": problems, "warnings": warnings}
    return _validate_one(capability_dir)


def _validate_one(capability_dir: Path) -> dict:
    """Enforce the Agent-Skills authoring rules on ONE skill package."""
    capability_dir = Path(capability_dir)
    problems: list[str] = []
    warnings: list[str] = []

    skill_md = capability_dir / "SKILL.md"
    if not skill_md.exists():
        return {"ok": False, "problems": ["no SKILL.md in the package"], "warnings": []}

    text = skill_md.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    name = fm.get("name", "")
    if not name:
        problems.append("frontmatter missing 'name'")
    elif not NAME_RE.match(name):
        problems.append(f"name {name!r} must be <=64 chars, lowercase [a-z0-9-]")
    if "anthropic" in name.lower() or "claude" in name.lower():
        problems.append("name must not contain 'anthropic' or 'claude'")
    if XML_TAG_RE.search(name):
        problems.append("name must not contain XML tags")

    desc = fm.get("description", "")
    if not desc.strip():
        problems.append("frontmatter missing a non-empty 'description'")
    else:
        if len(desc) > LONG_DESC_CHARS:
            problems.append(f"description is {len(desc)} chars (>{LONG_DESC_CHARS})")
        if XML_TAG_RE.search(desc):
            problems.append("description must not contain XML tags")
        if not re.search(r"\b(use when|when )\b", desc, re.I):
            warnings.append("description should say WHEN to use the skill "
                            "('Use when …') — it is the primary triggering signal")
        # point-of-view drift: descriptions must be third person.
        if re.search(r"(?<![A-Za-z])I(?![A-Za-z])|I'?m\b|I can\b|you can help", desc):
            warnings.append("description should be third person (e.g. 'Processes X "
                            "…'), not first person ('I can …') — POV drift hurts discovery")
        # all-caps imperatives over-trigger current models.
        if re.search(r"\b(CRITICAL|ALWAYS|MUST|NEVER)\b", desc):
            warnings.append("avoid all-caps CRITICAL/ALWAYS/MUST/NEVER in the "
                            "description — it over-triggers; say plainly 'Use when …'")
        # the listing shows description + when_to_use truncated at 1,536 chars.
        if len(desc) > LISTING_CAP_CHARS - 256:
            warnings.append(f"description is {len(desc)} chars; the listing truncates "
                            f"description + when_to_use at {LISTING_CAP_CHARS} — "
                            "front-load the key use case so it survives truncation")

    n_body = body.count("\n") + 1
    if n_body > MAX_BODY_LINES:
        warnings.append(f"SKILL.md body is {n_body} lines (>{MAX_BODY_LINES}); "
                        "split detail into references/ (progressive disclosure)")
    body_tokens = len(body) // CHARS_PER_TOKEN
    if body_tokens > MAX_BODY_TOKENS:
        warnings.append(f"SKILL.md body is ~{body_tokens} tokens (>{MAX_BODY_TOKENS}); "
                        "it is a recurring per-session cost — move detail into references/")

    refs = capability_dir / "references"
    if refs.is_dir():
        for sub in refs.iterdir():
            if sub.is_dir():
                warnings.append(f"references/{sub.name}/ is nested >1 level deep; "
                                "keep references one level deep")
        for f in refs.glob("*.md"):
            ln = f.read_text(encoding="utf-8").count("\n") + 1
            if ln > LONG_REF_LINES and "## " not in f.read_text(encoding="utf-8")[:1500]:
                warnings.append(f"references/{f.name} is {ln} lines without an early "
                                "table of contents")

    # broken reference links the body points at
    for rel in re.findall(r"\(((?:references|scripts|assets)/[^)\s]+)\)", body):
        if not (capability_dir / rel).exists():
            warnings.append(f"SKILL.md references '{rel}' which does not exist")

    return {"ok": not problems, "name": name, "problems": problems, "warnings": warnings}
