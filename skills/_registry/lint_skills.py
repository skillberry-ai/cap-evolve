#!/usr/bin/env python3
"""Dogfood the skill-package authoring lint on cap-evolve's OWN bundled skills.

The framework ships `skills/capabilities/skill-package/scripts/abstract.py` to
enforce the Agent-Skills authoring rules on *user* skills. This script points the
same validator at `skills/*/*/SKILL.md` so the framework is held to the bar it
advertises, and fails the build (nonzero exit) on any violation.

Two deliberate differences from the shipped `validate()`:

1. **Structural authoring warnings are ERRORS here.** `validate()` reports body
   size / reference nesting / missing-TOC / broken links as *warnings* because an
   optimizer mid-run should not be hard-blocked by a style budget. For the repo's
   own skills there is no such excuse, so `PROMOTED` turns them into failures.
   Description *style* heuristics (POV, all-caps, "say WHEN", truncation risk) stay
   advisory — they are judgement calls, not measurable violations.
2. **Empty template placeholders fail** (CONTRIBUTING's "only when filled" rule):
   a `references/*.md` file that is a stub or still carries TODO/TBD/FIXME
   scaffolding. Scoped to references on purpose: `XXX` appears legitimately in four
   SKILL.md bodies (`run_XXXX` in example commands), so scanning bodies would be
   noise. A SKILL.md body is NOT placeholder-checked.

Discovery is dynamic (a glob, never a committed list) so a NEW skill is linted the
day it lands. The anti-vacuity guard cross-checks that glob against the committed
`manifest.json` — two independent views of the same tree that must agree — so a
rename/move/deletion fails loudly even when an addition in the same commit keeps the
total unchanged. CI pins the manifest itself with `git diff --exit-code`, so neither
side can drift unreviewed and there is no magic floor anyone must remember to bump.

Usage: python skills/_registry/lint_skills.py [skills_root]
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

# `validate()` warnings that are objectively measurable authoring violations, keyed
# by a stable fragment of the message. Anything not matched here stays advisory.
# Coupled to abstract.py's wording on purpose; test_skill_authoring_lint.py proves
# each of these still fires, so a reworded warning breaks the test, not the lint.
PROMOTED = (
    "lines (>",              # body over MAX_BODY_LINES
    "tokens (>",             # body over MAX_BODY_TOKENS
    "level deep",            # references/ nested more than one level
    "table of contents",     # long reference with no early TOC
    "does not exist",        # SKILL.md points at a missing reference/script
)

PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|<(placeholder|fill[- ]in)>", re.I)
MIN_REF_LINES = 5           # below this a reference file is a stub, not a document


def _load_validator(skills_root: Path):
    path = skills_root / "capabilities" / "skill-package" / "scripts" / "abstract.py"
    if not path.is_file():
        raise SystemExit(f"lint_skills: cannot find the validator at {path}")
    spec = importlib.util.spec_from_file_location("skill_package_abstract", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest_drift(skills_root: Path) -> str:
    """Anti-vacuity: the glob and the committed manifest are two independent views of
    the same tree and must agree. A floor (`n < 20`) misses rename-away + add-new in
    one commit; comparing the PATH SETS catches it, and needs no magic number."""
    manifest = skills_root / "_registry" / "manifest.json"
    if not manifest.is_file():
        return f"the committed manifest is missing at {manifest}"
    listed = {s["path"] for s in
              json.loads(manifest.read_text(encoding="utf-8"))["skills"].values()}
    found = {p.parent.relative_to(skills_root).as_posix()
             for p in skills_root.glob("*/*/SKILL.md")}
    if found == listed:
        return ""
    return (f"{len(found)} skill package(s) on disk do not match the {len(listed)} in "
            f"manifest.json — on disk only: {sorted(found - listed) or 'none'}; in "
            f"manifest only: {sorted(listed - found) or 'none'}. A skill was "
            f"renamed/moved/removed; rebuild the manifest and re-review coverage")


def _placeholder_errors(skill_dir: Path) -> list[str]:
    """Empty / still-templated reference files (CONTRIBUTING: 'only when filled')."""
    errors = []
    refs = skill_dir / "references"
    if not refs.is_dir():
        return errors
    for f in sorted(refs.rglob("*.md")):
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(skill_dir).as_posix()
        if len(text.strip().splitlines()) < MIN_REF_LINES:
            errors.append(f"{rel} is an empty/stub reference "
                          f"(<{MIN_REF_LINES} lines) — fill it or delete it")
        hit = PLACEHOLDER_RE.search(text)
        if hit:
            errors.append(f"{rel} still contains the template placeholder "
                          f"{hit.group(0)!r}")
    return errors


def lint(skills_root: Path) -> tuple[dict[str, list[str]], list[str], int]:
    """Return (per-skill errors, per-skill advisories, number of skills linted)."""
    validator = _load_validator(skills_root)
    errors: dict[str, list[str]] = {}
    advisories: dict[str, list[str]] = {}
    skills = sorted(skills_root.glob("*/*/SKILL.md"))
    for skill_md in skills:
        skill_dir = skill_md.parent
        key = skill_dir.relative_to(skills_root).as_posix()
        v = validator.validate(skill_dir)
        errs = list(v["problems"])
        advs = []
        for w in v["warnings"]:
            (errs if any(frag in w for frag in PROMOTED) else advs).append(w)
        errs += _placeholder_errors(skill_dir)
        if errs:
            errors[key] = errs
        if advs:
            advisories[key] = advs
    return errors, advisories, len(skills)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "skills").resolve()
    errors, advisories, n = lint(root)

    print(f"skill authoring lint — {n} skill package(s) under {root}")
    for key in sorted(errors):
        for e in errors[key]:
            print(f"  ERROR   {key}: {e}")
    for key in sorted(advisories):
        for a in advisories[key]:
            print(f"  advise  {key}: {a}")

    drift = _manifest_drift(root)
    if drift:
        print(f"  ERROR   discovery: {drift}")
        return 1
    if errors:
        print(f"FAIL — {sum(len(v) for v in errors.values())} authoring violation(s) "
              f"in {len(errors)} skill(s)")
        return 1
    print(f"OK — {n} skill packages pass the authoring bar "
          f"({len(advisories)} advisory note(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
