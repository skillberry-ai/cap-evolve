"""Link contract for this skill: every relative link resolves, and no reference links to another.

Two failures this catches, both silent in review:
  * a body pointer to `references/<x>.md` that was renamed or never created — the agent follows
    the pointer, finds nothing, and improvises the depth the reference was supposed to carry;
  * a reference that links to another reference. References are ONE level deep because the agent
    may read only part of either one, so a ref->ref hop can leave it acting on half a rule.

Run: python scripts/linkcheck.py   (prints JSON, exits non-zero on any problem)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    problems: list[str] = []
    checked = 0
    files = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
    for f in files:
        rel_f = f.relative_to(SKILL)
        for target in LINK.findall(f.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            checked += 1
            path, _, anchor = target.partition("#")
            resolved = (f.parent / path).resolve()
            if not resolved.is_file():
                problems.append(f"{rel_f}: broken relative link -> {target}")
                continue
            if anchor:
                slugs = {
                    re.sub(r"[^a-z0-9\- ]", "", line.lstrip("#").strip().lower()).replace(" ", "-")
                    for line in resolved.read_text(encoding="utf-8").splitlines()
                    if line.startswith("#")
                }
                if anchor not in slugs:
                    problems.append(f"{rel_f}: link {target} names a heading that does not exist")
            if f.parent.name == "references" and resolved.parent.name == "references":
                problems.append(
                    f"{rel_f}: links to another reference ({path}) — references are one level deep")

    print(json.dumps({"files": len(files), "relative_links": checked,
                      "ok": not problems, "problems": problems}, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
