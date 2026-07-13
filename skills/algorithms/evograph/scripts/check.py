"""Behavioral contract for evograph (AGENT MODE ONLY).

evograph has no deterministic loop, so — unlike gepa/skillopt — there is nothing to
run offline. Instead this check pins the contract that makes evograph safe and
discoverable:

  1. its ``run.py`` REFUSES a deterministic invocation (exit 2 + an "agent-mode only"
     directive) rather than faking a deterministic loop;
  2. the SKILL.md declares the agent-mode round loop AND the honesty rules
     (sealed test via finalize, primary-metric gating);
  3. every referenced doc exists (the wiki-format contract the dashboard reads).
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

    # 2: SKILL.md declares the loop + honesty contract.
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for needle, label in [
        ("Round loop", "agent-mode round loop"),
        ("finalize", "seal via cap-evolve finalize"),
        ("primary metric", "primary-metric gating"),
        ("orchestration_mode: agent", "agent-mode gating"),
    ]:
        c.check(needle in skill, f"SKILL.md missing: {label!r} ({needle!r})", note=f"SKILL.md declares {label}")

    # 3: the referenced wiki-format docs exist.
    for ref in ("clustering.md", "graph.md", "dashboard.md", "cost.md"):
        c.check((SKILL_DIR / "references" / ref).exists(),
                f"missing reference: references/{ref}", note=f"references/{ref} present")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
