"""evograph — AGENT MODE ONLY entry.

evograph has no deterministic engine: its weakness-graph loop is driven by the
coding agent (see SKILL.md). Under ``orchestration_mode: agent`` cap-evolve runs
intake → check → baseline and then HANDS OFF to the agent (see cli.py), so this
run.py is never invoked for a real evograph run.

If it IS invoked — i.e. someone selected ``algorithm_skill: evograph`` with
``orchestration_mode: deterministic`` — fail loudly with a clear directive rather
than pretending to run a deterministic loop. This keeps the honesty contract
explicit: there is no fake deterministic evograph.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

ALGO = "evograph"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=ALGO)
    # Accept (and ignore) the standard algorithm flags so a mis-configured
    # deterministic invocation reaches our clear error instead of an argparse crash.
    p.add_argument("--run-dir")
    p.add_argument("--project")
    p.add_argument("--optimizer")
    p.add_argument("--max-iterations")
    p.add_argument("--n-trials")
    p.add_argument("--gate-mode")
    p.add_argument("--k-se")
    p.add_argument("--store")
    p.parse_known_args(argv)

    print(json.dumps({
        "algorithm": ALGO,
        "error": "evograph is agent-mode only",
        "detail": (
            "evograph has no deterministic engine. Set `orchestration_mode: agent` in "
            "capevolve.yaml and run it agent-driven: cap-evolve does intake/check/baseline "
            "then hands the loop to the coding agent, which follows this skill's "
            "'Step 2 — Round loop' and seals with `cap-evolve finalize`."
        ),
    }))
    return 2


if __name__ == "__main__":
    sys.exit(main())
