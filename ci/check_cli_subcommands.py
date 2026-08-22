#!/usr/bin/env python3
"""Fail if a doc or skill invokes a `cap-evolve <subcommand>` the CLI does not implement.

Docs and several algorithm skills used to instruct agents to invoke the finalize and
report PHASES as if they were subcommands. Neither is (both are scripts, invoked by
`cap-evolve run` via `skill_run(step)`), so an agent following them ran a command that
fails at the end of a run that may have cost real money (issue #203).

This file names no phantom command itself -- on purpose: the check scans `ci/` too, so a
worked example here would need an exception mechanism, and an exception mechanism is the
hole every future phantom slips through.

The valid set is READ OUT OF THE CODE -- the `COMMANDS` dict in `core/cap_evolve/cli.py`,
parsed with `ast` so nothing needs installing -- not hardcoded here, so it stays correct
as commands are added or removed.

Only backticked/fenced invocations are checked; prose like "cap-evolve optimizes any
capability" is not a command. Usage: `python ci/check_cli_subcommands.py [root ...]`.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "core" / "cap_evolve" / "cli.py"
# .py/.sh are in here because the two worst #203 sites were CODE, not prose: the
# agent-mode handoff JSON printed by cli.py and the Stop-hook nudge in plugins/.
SUFFIXES = {".md", ".yaml", ".yml", ".txt", ".py", ".sh"}
DEFAULT_ROOTS = ("skills", "docs", "templates", "plugins", "ci", "site", "examples",
                 "core", "README.md", "RUN.md", "llms.txt")
# CHANGELOG records what past releases claimed; built run artifacts are generated.
SKIP = ("CHANGELOG.md", "core/build/", "node_modules/", "/run_full/", "/dist/")

# The two forms a real invocation takes: a backticked span and a line
# inside a ``` fence. Unfenced prose ("cap-evolve runs intake ...") is not a command and is
# deliberately not matched. ponytail: no shell parsing -- a fence line must be the command
# at column 0 (indented fence lines are prose notes); widen if a phantom hides mid-pipeline.
INLINE = re.compile(r"`+cap-evolve\s+([a-z][a-z0-9-]*)")
FENCED = re.compile(r"^\$? ?cap-evolve\s+([a-z][a-z0-9-]*)")
# ...and an unfenced line that is plainly a copy-pasteable command (carries a `--flag`).
BARE = re.compile(r"^\$? ?cap-evolve\s+([a-z][a-z0-9-]*)(?=.*\s--)")


def invocations(text):
    """Yield (subcommand, line_no) for every real `cap-evolve <sub>` invocation."""
    fenced = False
    for n, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        pats = (FENCED,) if fenced else (INLINE, BARE)
        for m in (m for pat in pats for m in pat.finditer(line)):
            yield m.group(1), n


def cli_commands() -> set[str]:
    """The subcommand names `cap-evolve` actually dispatches, straight from cli.py."""
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "COMMANDS" for t in node.targets
        ):
            names |= {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    if not names:
        sys.exit(f"error: no COMMANDS table found in {CLI} -- update this check")
    return names | {"help", "version"}  # -h/--help/-V/--version aliases


def files(roots):
    for r in roots:
        p = ROOT / r
        for f in ([p] if p.is_file() else sorted(p.rglob("*"))):
            rel = f.relative_to(ROOT).as_posix()
            if f.is_file() and f.suffix in SUFFIXES and not any(s in rel for s in SKIP):
                yield f, rel


def main(argv) -> int:
    valid = cli_commands()
    bad = []
    for f, rel in files(argv or list(DEFAULT_ROOTS)):
        for sub, line in invocations(f.read_text(encoding="utf-8", errors="replace")):
            if sub not in valid:
                bad.append(f"{rel}:{line}: `cap-evolve {sub}` is not a subcommand")
    if bad:
        print("\n".join(bad))
        print(f"\n{len(bad)} phantom cap-evolve subcommand reference(s).")
        print(f"Valid: {' '.join(sorted(valid))}")
        print("Phases (finalize/report/baseline/...) are SCRIPTS: run "
              "`python skills/phases/<phase>/scripts/run.py`, or `/cap-evolve:<phase>`, "
              "or let `cap-evolve run` sequence them.")
        return 1
    print(f"ok: no phantom cap-evolve subcommands (valid: {' '.join(sorted(valid))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
