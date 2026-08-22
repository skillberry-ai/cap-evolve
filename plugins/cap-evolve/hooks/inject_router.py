#!/usr/bin/env python3
"""SessionStart — inject the using-cap-evolve router as additionalContext.

Best-effort: at session start, if the cwd looks like a cap-evolve project (or an
in-progress run), nudge the model toward the ``using-cap-evolve`` router so a
plain "optimize <X>" request is recognized and routed to ``intake`` rather than
improvised. This is *context*, not enforcement — the honesty rules are enforced
by the PreToolUse / Stop hooks and by core.

Claude Code SessionStart contract: a hook may print JSON on stdout of the shape

    {
      "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "<text prepended to the session context>"
      }
    }

We emit that envelope (exit 0). If the cwd is unrelated, we stay silent (print
nothing, exit 0) so the plugin is invisible on other projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as H  # noqa: E402


_CONTEXT = (
    "cap-evolve is installed. When the user wants an agent capability (a skill, a "
    "tool/MCP surface, a system/agent prompt) to score higher on an eval — \"optimize "
    "my skill\", \"raise the pass rate on these tasks\", \"my agent keeps failing these "
    "cases\" — load the `/cap-evolve:using-cap-evolve` router skill first. It resolves "
    "the on-disk state and names the next command. There are three ways to run: the "
    "standalone phase chain (`/cap-evolve:intake` -> implement-and-check -> baseline -> "
    "the algorithm -> finalize -> report); `cap-evolve run --spec .capevolve/project/"
    "capevolve.yaml`, which presumes intake already happened and enforces the check "
    "gate before spending budget; or, with `orchestration_mode: agent` in the spec, "
    "`cap-evolve run` stops after baseline and hands the loop back to the agent, with "
    "no sealed-test number until the finalize phase script seals it. Honesty discipline "
    "(sealed test, val-only gate) is enforced by core and by this plugin's hooks — do "
    "not edit the test split, test rollouts, or gold files, and do not finish an "
    "iteration while `cap-evolve check` is red."
)


def _looks_like_capevolve(cwd: Path) -> bool:
    if H.find_run_dir(cwd) is not None:
        return True
    for parent in [cwd, *cwd.parents]:
        if (parent / ".capevolve" / "project").is_dir():
            return True
        # repo checkout (dev) — RUN.md + skills/ present
        if (parent / "RUN.md").exists() and (parent / "skills").is_dir():
            return True
    return False


def main() -> int:
    try:
        payload = H.read_payload()
        cwd = H.hook_cwd(payload)
        if not _looks_like_capevolve(cwd):
            return 0  # silent on unrelated projects
        out = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": _CONTEXT,
            }
        }
        print(json.dumps(out))
        return 0
    except Exception as e:
        print(f"cap-evolve inject_router hook: internal error ignored: {e}",
              file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
