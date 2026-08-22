"""Report the progressive-disclosure token budget of a skill package.

Level 2 (the SKILL.md body) is loaded on every trigger and stays in context for
the whole session — a *recurring* token cost — so it has a budget (<=500 lines;
~5k tokens is this repo's own heuristic). Level 3 costs **zero** context until
used: a reference until it is read, a script until it is run (and a script's
source is never loaded at all — only its output). So the report states
``context_cost: 0`` for both, and inventories ``scripts/`` — the deterministic
surface — instead of only sizing the cheap thing.

Deterministic, dependency-free (no cap-evolve bootstrap) — run it directly:

    python scripts/token_report.py --path <skill_dir>
    python scripts/token_report.py --self-check

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
    # Level 3 is free until used — say so, so a big reference is not mistaken for
    # an expensive one and the optimizer reads the budget correctly.
    out["references_context_cost"] = 0
    out["scripts"] = _scripts(skill_dir)
    out["scripts_context_cost"] = 0        # source never loads; only the output costs
    return out


def _scripts(skill_dir: Path) -> list[dict]:
    """Inventory the deterministic surface: size, entry point, declared self-check."""
    d = skill_dir / "scripts"
    if not d.is_dir():
        return []
    rows = []
    for f in sorted(d.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        try:
            src = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            src = ""
        rows.append({"file": f.relative_to(skill_dir).as_posix(),
                     "bytes": f.stat().st_size,
                     "entry_point": '__main__' in src or f.suffix == ".sh",
                     "self_check": "--self-check" in src})
    return rows


def _self_check() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        pkg = Path(d)
        (pkg / "SKILL.md").write_text("---\nname: t\ndescription: d\n---\n# t\nbody\n",
                                      encoding="utf-8")
        (pkg / "scripts").mkdir()
        (pkg / "scripts" / "h.py").write_text(
            'if __name__ == "__main__":\n    pass  # --self-check\n', encoding="utf-8")
        r = report(pkg)
    assert r["scripts"] and r["scripts"][0]["file"] == "scripts/h.py", r
    assert r["scripts"][0]["entry_point"] and r["scripts"][0]["self_check"], r
    assert r["scripts_context_cost"] == 0 and r["references_context_cost"] == 0, r
    assert r["body_lines"] > 0 and r["over_budget"] is False, r
    print(json.dumps({"self_check": "ok"}))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="token-report")
    p.add_argument("--path", help="skill package dir (contains SKILL.md)")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args(argv)
    if args.self_check:
        return _self_check()
    if not args.path:
        p.error("--path is required (or use --self-check)")
    print(json.dumps(report(Path(args.path)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
