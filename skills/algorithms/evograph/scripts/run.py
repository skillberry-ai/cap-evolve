"""evograph — DEPRECATED, and never had a deterministic engine.

evograph is deprecated (see SKILL.md): use ``agent-optimize`` for agent-mode search,
or ``hill-climb`` / ``gepa`` / ``skillopt`` for a deterministic loop.

It also never had a deterministic engine — its weakness-graph loop was agent-driven,
so under ``orchestration_mode: agent`` cap-evolve ran intake → check → baseline and
then HANDED OFF to the agent (see cli.py); this run.py was never invoked for a real
evograph run.

If it IS invoked — i.e. someone selected ``algorithm_skill: evograph`` with
``orchestration_mode: deterministic`` — fail loudly with a clear directive rather
than pretending to run a deterministic loop. This keeps the honesty contract
explicit: there is no fake deterministic evograph, and now no reason to want one.
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
        "error": "evograph is agent-mode only, and is DEPRECATED",
        "detail": (
            "evograph has no deterministic engine and is deprecated. Set "
            "`algorithm_skill: agent-optimize` (with `orchestration_mode: agent`) for the "
            "same per-cluster fan-out behind the val significance gate, or "
            "`hill-climb` | `gepa` | `skillopt` for a deterministic loop. See "
            "skills/algorithms/evograph/SKILL.md for why."
        ),
    }))
    return 2


if __name__ == "__main__":
    sys.exit(main())
