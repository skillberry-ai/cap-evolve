"""Behavioral contract for evograph (DEPRECATED, agent mode only).

evograph never had a deterministic loop, and it is now deprecated, so there is still
nothing to run offline. This check pins what must stay true of the deprecated skill:

  1. its ``run.py`` REFUSES a deterministic invocation (exit 2 + an "agent-mode only"
     directive) rather than faking a deterministic loop;
  2. the SKILL.md marks itself DEPRECATED and names the replacement (``agent-optimize``),
     so nobody starts a new run on it by accident;
  3. every referenced doc exists — above all the wiki-format contract the dashboard's
     Weakness-graph tab reads, which is the reason this directory still exists.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run

SKILL_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    c = Checker("evograph")
    run = import_run()
    c.require_main(run)

    # 1: deterministic invocation is refused loudly (agent-mode only).
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = run.main(["--run-dir", "x", "--project", "y", "--optimizer", "mock"])
    out = buf.getvalue()
    c.check(rc == 2, f"deterministic run.py should exit 2, got {rc}", note="run.py refuses deterministic mode")
    try:
        payload = json.loads(out)
    except Exception:
        payload = {}
    c.check("agent-mode only" in payload.get("error", ""),
            "run.py did not emit the agent-mode-only error",
            note="clear agent-mode directive emitted")

    # 2: SKILL.md is honestly marked deprecated and points somewhere better.
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for needle, label in [
        ("DEPRECATED", "itself deprecated"),
        ("agent-optimize", "the agent-mode replacement"),
        ("hill-climb", "the deterministic replacements"),
        ("no deterministic engine", "that it has no deterministic engine"),
    ]:
        c.check(needle in skill, f"SKILL.md missing: {label!r} ({needle!r})", note=f"SKILL.md declares {label}")

    # 3: the referenced wiki-format docs exist.
    for ref in ("clustering.md", "graph.md", "dashboard.md"):
        c.check((SKILL_DIR / "references" / ref).exists(),
                f"missing reference: references/{ref}", note=f"references/{ref} present")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
