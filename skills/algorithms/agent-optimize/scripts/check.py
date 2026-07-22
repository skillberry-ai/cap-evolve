"""Contract: agent-optimize is an agent-mode-only algorithm.

It has no deterministic loop, so its behavioral contract is:
  * ``run.main()`` refuses a deterministic invocation (returns non-zero with a
    clear fix), so selecting it without ``orchestration_mode: agent`` fails loudly
    rather than no-opping into a misleading seed-vs-seed finalize; and
  * ``SKILL.md`` carries the "Agent-mode loop" the agent follows plus the
    honesty invariants that keep full autonomy honest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run, quiet


def main() -> int:
    c = Checker("agent-optimize")
    run = import_run()
    c.require_main(run)

    # The deterministic-invocation guard must fire (non-zero) and stay quiet on JSON.
    with quiet():
        rc = run.main(["--run-dir", "R", "--project", "P", "--optimizer", "x"])
    c.check(rc != 0, "run.main must refuse a deterministic invocation (non-zero)",
            note="deterministic invocation is rejected with a fix message")

    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    c.check("## Agent-mode loop" in skill, "SKILL.md missing the '## Agent-mode loop' section")
    c.check("Phase 0" in skill, "SKILL.md missing the Phase-0 understanding step")
    c.check("Honesty invariants" in skill, "SKILL.md missing the honesty invariants section")
    for needle in ("FULL val", "stop_condition", "finalize"):
        c.check(needle in skill, f"SKILL.md missing honesty/loop marker: {needle!r}")
    c.note("agent-mode-only algorithm: loop + honesty invariants documented in SKILL.md")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
