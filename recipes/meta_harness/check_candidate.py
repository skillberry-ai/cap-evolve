#!/usr/bin/env python3
"""Proposer-side candidate check for the exp895 Meta-Harness arm (stands in for upstream's
`uv run python -c "from agents.<name> import *; print('OK')"` validation step).

Stdlib only, Python >= 3.9 (it runs inside the optimizer sandbox). It holds NO task ids and reads nothing
outside the candidate directory. The outer loop runs the authoritative checks (the adapter's placeholder
contract, skills-tree check, and cap-evolve's helper lint + smoke) before any rollout.

Usage: python check_candidate.py candidates/<name>      -> prints CHECK_OK or CHECK_FAIL lines, exit 0/1
"""
import re
import string
import subprocess
import sys
from pathlib import Path

REQUIRED = {"instruction", "spreadsheet_path", "spreadsheet_content", "instruction_type", "answer_position",
            "output_path"}
OPTIONAL = {"max_turns"}
COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)
GOLD_NAME = re.compile(r"(_answer|_golden|^golden|^answer)", re.I)
SUFFIXES = {".py", ".md", ".json", ".txt", ".yaml", ".yml"}
# Import helpers with the exp895 venv python (has openpyxl/pandas, like the agent's kernel) when it is visible;
# inside the optimizer sandbox `python3` is the OS python, which may lack them.
_VENV_PY = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895/venv/bin/python")
PY = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def main(argv):
    if len(argv) != 2:
        print("usage: check_candidate.py candidates/<name>")
        return 2
    c = Path(argv[1])
    bad = []
    for f in ("prompt.md", "task_template.md"):
        if not (c / f).is_file():
            bad.append(f"{f}: missing")
    if (c / "task_template.md").is_file():
        text = COMMENT.sub("", (c / "task_template.md").read_text(encoding="utf-8"), count=1)
        text = text.replace("{skills_root}", "skills")
        try:
            found = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            miss, unk = sorted(REQUIRED - found), sorted(found - REQUIRED - OPTIONAL)
            if miss:
                bad.append("task_template.md: missing required placeholder(s) " + ", ".join("{%s}" % m for m in miss))
            if unk:
                bad.append("task_template.md: unknown placeholder(s) " + ", ".join("{%s}" % u for u in unk)
                           + " (write a literal brace as {{ or }})")
        except ValueError as e:
            bad.append(f"task_template.md: not a valid format string ({e}); a literal brace must be {{{{ or }}}}")
    sk = c / "skills"
    if sk.is_dir():
        for p in sorted(sk.rglob("*")):
            if "__pycache__" in p.parts or p.name == ".gitkeep":
                continue
            rel = p.relative_to(c).as_posix()
            if p.is_symlink():
                bad.append(f"{rel}: symlink")
            elif p.is_file() and GOLD_NAME.search(p.name):
                bad.append(f"{rel}: gold-like file name")
            elif p.is_file() and p.suffix.lower() not in SUFFIXES:
                bad.append(f"{rel}: file type {p.suffix or '(none)'} not allowed in skills/")
        for md in sorted(sk.glob("*/SKILL.md")):
            t = md.read_text(encoding="utf-8", errors="replace")
            m = re.match(r"---\s*\n(.*?)\n---\s*\n?", t, re.S)
            if not m or not re.search(r"(?m)^name:\s*\S", m.group(1)) or not re.search(r"(?m)^description:\s*\S", m.group(1)):
                bad.append(f"{md.relative_to(c).as_posix()}: needs YAML frontmatter with name: and description:")
        for d in sorted(p for p in sk.iterdir() if p.is_dir()):
            if not (d / "SKILL.md").is_file() and any(d.rglob("*.py")):
                bad.append(f"skills/{d.name}: has scripts but no SKILL.md (the agent would never learn they exist)")
        for f in sorted(sk.glob("*/scripts/*.py")):
            rel = f.relative_to(c).as_posix()
            try:
                compile(f.read_text(encoding="utf-8"), rel, "exec")
            except SyntaxError as e:
                bad.append(f"{rel}: SyntaxError line {e.lineno}: {e.msg}")
                continue
            # import in a fresh interpreter (same python as this check), 20 s cap, as the kernel would
            code = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('m', sys.argv[1]); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('IMPORT_OK')")
            try:
                r = subprocess.run([PY, "-I", "-B", "-c", code, str(f)], capture_output=True, text=True,
                                   timeout=20, cwd=str(c))
                if "IMPORT_OK" not in r.stdout:
                    tail = (r.stderr.strip().splitlines() or ["no output"])[-1]
                    bad.append(f"{rel}: import failed: {tail[:300]}")
            except subprocess.TimeoutExpired:
                bad.append(f"{rel}: import took > 20 s")
    for b in bad:
        print("CHECK_FAIL", b)
    if not bad:
        print("CHECK_OK", c)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
