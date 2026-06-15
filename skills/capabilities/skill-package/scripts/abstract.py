"""skill-package capability — optimize an Agent Skill package (SKILL.md + refs + scripts).

A skill package is a directory: a required ``SKILL.md`` (YAML frontmatter
``name``/``description`` + a Markdown body) plus optional ``references/`` (docs
loaded on demand), ``scripts/`` (executables), and ``assets/``. Optimizing a skill
means editing that text to improve how a downstream agent uses it.

``validate`` here encodes the skill-creator / Agent-Skills authoring rules so the
optimizer can't drift into an invalid package:
  - frontmatter has ``name`` (<=64 chars, [a-z0-9-], no "anthropic"/"claude") and
    a non-empty ``description`` (<=1024 chars) that says WHAT + WHEN ("use when").
  - SKILL.md body stays under ~500 lines (progressive disclosure budget).
  - references are one level deep and any long reference (>300 lines) has a TOC.
  - referenced files that the body points at actually exist.

Edit ops (mirrored by the mock optimizer): {"file","op":"set|append|ensure_contains","text"}.
"""

from __future__ import annotations

import re
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)
MAX_BODY_LINES = 500
LONG_REF_LINES = 300


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


def materialize(capability_dir: Path) -> dict:
    """Flatten SKILL.md + references into named text components."""
    capability_dir = Path(capability_dir)
    parts = {}
    skill_md = capability_dir / "SKILL.md"
    if skill_md.exists():
        parts["SKILL.md"] = skill_md.read_text(encoding="utf-8")
    refs = capability_dir / "references"
    if refs.is_dir():
        for f in sorted(refs.glob("*.md")):
            parts[f"references/{f.name}"] = f.read_text(encoding="utf-8")
    return parts


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
    """Enforce the Agent-Skills authoring rules. Returns {ok, problems, warnings}."""
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

    desc = fm.get("description", "")
    if not desc.strip():
        problems.append("frontmatter missing a non-empty 'description'")
    else:
        if len(desc) > 1024:
            problems.append(f"description is {len(desc)} chars (>1024)")
        if not re.search(r"\b(use when|when )\b", desc, re.I):
            warnings.append("description should say WHEN to use the skill "
                            "('Use when …') — it is the primary triggering signal")

    n_body = body.count("\n") + 1
    if n_body > MAX_BODY_LINES:
        warnings.append(f"SKILL.md body is {n_body} lines (>{MAX_BODY_LINES}); "
                        "split detail into references/ (progressive disclosure)")

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
