#!/usr/bin/env python3
"""Dogfood the skill-package authoring lint on cap-evolve's OWN bundled skills.

The framework ships `skills/capabilities/skill-package/scripts/abstract.py` to
enforce the Agent-Skills authoring rules (skill-creator's progressive-disclosure
budget, frontmatter shape, one-level references) on *user* skills. This script
points that same validator at `skills/*/*/SKILL.md`, so the framework is held to
the bar it advertises in CONTRIBUTING.md instead of only selling it.

Structural authoring warnings are ERRORS here. `validate()` reports body size /
reference depth / missing-TOC / broken links as *warnings* because an optimizer
mid-run should not be hard-blocked by a style budget. For the repo's own skills
there is no such excuse, so `PROMOTED` turns them into failures. Description
*style* heuristics (POV, all-caps, "say WHEN", truncation risk) stay advisory —
they are judgement calls, not measurable violations.

Discovery is a glob, never a committed list, so a NEW skill is linted the day it
lands. The anti-vacuity guard cross-checks that glob against the committed
`manifest.json` — two independent views of one tree that must agree — so a
rename/move/deletion fails loudly even when an addition in the same commit keeps
the count unchanged.

`--baseline FILE` records the violations that are already known (the skills are
being rewritten under issues #322-#339). Known lines are still printed but do not
affect the exit code; anything NEW fails. Delete the baseline to make the lint
absolute again.

Usage: python skills/_registry/lint_skills.py [skills_root] [--baseline[=FILE]]
                                              [--write-baseline[=FILE]]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# `validate()` warnings that are objectively measurable authoring violations, keyed
# by a stable fragment of the message. Anything not matched here stays advisory.
# Coupled to abstract.py's wording on purpose; test_skill_authoring_lint.py proves
# each of these still fires, so a reworded warning breaks the test, not the lint.
PROMOTED = (
    "lines (>",              # body over MAX_BODY_LINES
    "tokens (>",             # body over MAX_BODY_TOKENS
    "level deep",            # references nested, or a reference linking a reference
    "table of contents",     # long reference with no early TOC
    "does not exist",        # a relative link pointing at a missing file
)

DEFAULT_BASELINE = "authoring-baseline.txt"


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


def lint(skills_root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
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
        advs: list[str] = []
        for w in v["warnings"]:
            (errs if any(frag in w for frag in PROMOTED) else advs).append(w)
        if errs:
            errors[key] = errs
        if advs:
            advisories[key] = advs
    return errors, advisories, len(skills)


def _flatten(errors: dict[str, list[str]]) -> list[str]:
    """One stable `<skill>: <message>` line per violation — the baseline's format."""
    return [f"{key}: {e}" for key in sorted(errors) for e in errors[key]]


def _parse_argv(argv: list[str]) -> tuple[Path, dict[str, str]]:
    positional = [a for a in argv if not a.startswith("--")]
    opts = {}
    for a in argv:
        if a.startswith("--"):
            flag, _, value = a.partition("=")
            opts[flag] = value
    return Path(positional[0] if positional else "skills").resolve(), opts


def _baseline_path(root: Path, value: str) -> Path:
    return Path(value) if value else root / "_registry" / DEFAULT_BASELINE


def main(argv: list[str]) -> int:
    root, opts = _parse_argv(argv[1:])
    errors, advisories, n = lint(root)
    lines = _flatten(errors)

    if "--write-baseline" in opts:
        out = _baseline_path(root, opts["--write-baseline"])
        out.write_text("".join(f"{ln}\n" for ln in lines), encoding="utf-8")
        print(f"wrote {len(lines)} known violation(s) to {out}")
        return 0

    known: set[str] = set()
    if "--baseline" in opts:
        bl = _baseline_path(root, opts["--baseline"])
        if bl.is_file():
            known = {ln for ln in bl.read_text(encoding="utf-8").splitlines() if ln.strip()}

    print(f"skill authoring lint — {n} skill package(s) under {root}")
    for ln in lines:
        print(f"  {'known ' if ln in known else 'ERROR '} {ln}")
    for key in sorted(advisories):
        for a in advisories[key]:
            print(f"  advise {key}: {a}")

    drift = _manifest_drift(root)
    if drift:
        print(f"  ERROR  discovery: {drift}")
        return 1

    new = [ln for ln in lines if ln not in known]
    fixed = sorted(known - set(lines))
    if fixed:
        print(f"{len(fixed)} baselined violation(s) are now FIXED — remove them from "
              f"the baseline: {fixed}")
    if new:
        print(f"FAIL — {len(new)} authoring violation(s) not in the baseline "
              f"({len(lines) - len(new)} known, {len(advisories)} skill(s) with advisories)")
        return 1
    print(f"OK — {n} skill packages, no violations outside the baseline "
          f"({len(lines)} known, {len(advisories)} skill(s) with advisories)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
