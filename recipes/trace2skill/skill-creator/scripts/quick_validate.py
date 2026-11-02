#!/usr/bin/env python3
"""Minimal stand-in for the skill-creator `quick_validate.py` that Trace2Skill @ 3d0b52a1 calls but does not ship
(skill_evolver/skill_evolving_agent.py: QUICK_VALIDATE_SCRIPT = skills/skill-creator/scripts/quick_validate.py,
resolved against the CWD; run as `python quick_validate.py <skill_dir>`, exit 0 = valid, message on stdout).

The rules are exactly the ones Trace2Skill's own verification prompt states
(skill_evolver/prompts/parallel_evolving_agent/verification_system_prompt.txt, "Valid Skill Format"):
  * SKILL.md starts with a `---` YAML frontmatter block; required keys name, description; allowed keys only
    name, description, license, allowed-tools, metadata, compatibility
  * name: kebab-case [a-z0-9-]+, no leading/trailing/double hyphen, <= 64 chars
  * description: plain string, no < or >, <= 1024 chars; compatibility (optional) <= 500 chars
  * SKILL.md under 500 lines; each references/*.md under 300 lines
exp895 arm: trace2skill (issue skillberry-ai/cap-evolve#895 §7.5: "Add a minimal quick_validate.py stand-in").
"""
import re
import sys
from pathlib import Path

import yaml

ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def validate(skill_dir: Path) -> tuple[bool, str]:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return False, "SKILL.md not found"
    text = md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return False, "No YAML frontmatter found"
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return False, "Invalid frontmatter format"
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"
    if not isinstance(fm, dict):
        return False, "Frontmatter must be a YAML dictionary"
    extra = sorted(set(fm) - ALLOWED)
    if extra:
        return False, f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(extra)}. Allowed: {', '.join(sorted(ALLOWED))}"
    for key in ("name", "description"):
        if key not in fm:
            return False, f"Missing '{key}' in frontmatter"
    name = fm["name"]
    if not isinstance(name, str):
        return False, "Name must be a string"
    if not re.fullmatch(r"[a-z0-9-]+", name) or name.startswith("-") or name.endswith("-") or "--" in name:
        return False, f"Name '{name}' should be kebab-case (lowercase letters, digits and single inner hyphens)"
    if len(name) > 64:
        return False, f"Name is too long ({len(name)} characters, max 64)"
    desc = fm["description"]
    if not isinstance(desc, str):
        return False, "Description must be a string"
    if "<" in desc or ">" in desc:
        return False, "Description cannot contain angle brackets (< or >)"
    if len(desc) > 1024:
        return False, f"Description is too long ({len(desc)} characters, max 1024)"
    comp = fm.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or len(comp) > 500):
        return False, "Compatibility must be a string of at most 500 characters"
    n = len(text.splitlines())
    if n >= 500:
        return False, f"SKILL.md has {n} lines (must be under 500)"
    refs = skill_dir / "references"
    if refs.is_dir():
        for r in sorted(refs.glob("*.md")):
            k = len(r.read_text(encoding="utf-8", errors="replace").splitlines())
            if k >= 300:
                return False, f"references/{r.name} has {k} lines (must be under 300)"
    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
    ok, msg = validate(Path(sys.argv[1]))
    print(msg)
    sys.exit(0 if ok else 1)
