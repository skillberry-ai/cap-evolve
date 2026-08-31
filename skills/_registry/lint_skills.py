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
*style* heuristics (POV, all-caps, "say WHEN", truncation risk) and bundled-script
advisories (no declared `--self-check`, a risky import) stay advisory — they are
judgement calls, not measurable violations.

Discovery is a glob, never a committed list, so a NEW skill is linted the day it
lands. The anti-vacuity guard cross-checks that glob against the committed
`manifest.json` — two independent views of one tree that must agree — so a
rename/move/deletion fails loudly even when an addition in the same commit keeps
the count unchanged.

The lint is BLOCKING and there is no violation baseline. It shipped report-only
against a 14-violation baseline while the skills were rewritten under #322-#339;
that rewrite sweep cleared every one, so the baseline is empty and deleted, and the
next violation is a regression to fix rather than debt to record. (The baseline
machinery is in `git log -- skills/_registry/` if the tree ever needs it again.)

Usage: python skills/_registry/lint_skills.py [skills_root]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# `validate()` findings that are objectively measurable authoring violations, keyed by
# a stable fragment of the message. A warning matching one of these is promoted to an
# error; anything unmatched stays advisory. Coupled to abstract.py's wording on
# purpose: test_skill_authoring_lint.py proves each fragment is still reachable from a
# real violation, so a reworded message breaks the test instead of blinding the lint.
PROMOTED = (
    "lines (>",              # body over MAX_BODY_LINES
    "tokens (>",             # body over MAX_BODY_TOKENS
    "level deep",            # references nested, or a reference linking a reference
    "table of contents",     # long reference with no early TOC
    "does not exist",        # a relative link pointing at a missing file
)


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
             for p in skills_root.rglob("SKILL.md")
             if "_registry" not in p.parts}
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
    # rglob, not */*/: a component may GROUP its skills one level deeper
    # (interventions/llm-proxies/spa). A fixed depth would silently stop linting it,
    # which is exactly what the anti-vacuity guard below exists to catch.
    skills = sorted(p for p in skills_root.rglob("SKILL.md") if "_registry" not in p.parts)
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


def _flatten(findings: dict[str, list[str]]) -> list[str]:
    """One stable `<skill>: <message>` line per finding.

    Fully sorted, not just by skill: two runs in different processes must print
    byte-identical output, so no wobble in the order findings are produced may leak
    through. (`abstract.py` also sorts its reference iteration — this is the second
    belt, because output that depends on filesystem order fails on one machine only.)
    """
    return sorted(f"{key}: {m}" for key in findings for m in findings[key])


def main(argv: list[str]) -> int:
    positional = [a for a in argv[1:] if not a.startswith("--")]
    root = Path(positional[0] if positional else "skills").resolve()
    errors, advisories, n = lint(root)
    lines = _flatten(errors)

    print(f"skill authoring lint — {n} skill package(s) under {root}")
    for ln in lines:
        print(f"  ERROR  {ln}")
    for ln in _flatten(advisories):
        print(f"  advise {ln}")

    drift = _manifest_drift(root)
    if drift:
        print(f"  ERROR  discovery: {drift}")
        return 1
    if lines:
        print(f"FAIL — {len(lines)} authoring violation(s) "
              f"({len(advisories)} skill(s) with advisories)")
        return 1
    print(f"OK — {n} skill packages, no authoring violations "
          f"({len(advisories)} skill(s) with advisories)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
