"""Report the progressive-disclosure token budget of a skill package.

Level 2 (the SKILL.md body) is loaded on every trigger and stays in context for
the whole session — a *recurring* token cost — so it has a soft budget
(<500 lines / ~5k tokens). Level 3 references cost zero context until actually
read. This reporter estimates those costs (~chars/4) and flags body overruns, so
the optimizer can SEE the budget instead of guessing.

Deterministic, dependency-free (no cap-evolve bootstrap) — run it directly:

    python scripts/token_report.py --path <skill_dir>

Exit code is 0 always (advisory); the JSON `over_budget` flag carries the signal.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4
MAX_BODY_TOKENS = 5000
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---", re.S)


def _tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def report(skill_dir: Path) -> dict:
    skill_dir = Path(skill_dir)
    out: dict = {"skill_dir": str(skill_dir), "references": {}}

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"error": "no SKILL.md", **out}
    text = skill_md.read_text(encoding="utf-8")
    body = FRONTMATTER_RE.sub("", text, count=1)
    out["body_tokens"] = _tokens(body)
    out["body_lines"] = body.count("\n") + 1
    out["over_budget"] = out["body_tokens"] > MAX_BODY_TOKENS
    out["budget_tokens"] = MAX_BODY_TOKENS

    refs = skill_dir / "references"
    if refs.is_dir():
        for f in sorted(refs.glob("*.md")):
            out["references"][f.name] = _tokens(f.read_text(encoding="utf-8"))
    out["reference_tokens_total"] = sum(out["references"].values())
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="token-report")
    p.add_argument("--path", required=True, help="skill package dir (contains SKILL.md)")
    args = p.parse_args(argv)
    print(json.dumps(report(Path(args.path)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
