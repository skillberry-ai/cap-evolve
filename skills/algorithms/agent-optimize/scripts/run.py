"""agent-optimize — the fully-agentic, free-form optimization algorithm.

This algorithm has NO deterministic subprocess loop. The conversational agent
drives the whole search itself, following the "Agent-mode loop" in ``SKILL.md``:
understand the benchmark/inputs, run the baseline, then freely propose edits,
triage on task subsets, gate on FULL val, and stop when the free-text
``stop_condition`` is met — sealing once via the finalize phase.

Because agent mode short-circuits in ``cap-evolve run`` right after baseline (it
prints a handoff and returns *before* any algorithm subprocess is invoked), this
``run.py`` is never called on the happy path. It exists only as a loud guard: if
someone selects ``algorithm_skill: agent-optimize`` WITHOUT ``orchestration_mode:
agent`` (i.e. tries to run it deterministically), fail with a clear message rather
than silently no-op into a misleading seed-vs-seed finalize.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

ALGO = "agent-optimize"


def main(argv=None) -> int:
    # Accept the standard algorithm CLI seam so a deterministic invocation reaches
    # our guard message instead of an argparse crash.
    p = argparse.ArgumentParser(prog=ALGO)
    p.add_argument("--run-dir")
    p.add_argument("--project")
    p.add_argument("--optimizer")
    p.add_argument("--max-iterations", type=int, default=0)
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--gate-mode", default="auto")
    p.add_argument("--k-se", type=float, default=1.0)
    p.add_argument("--store", default="git")
    # Tolerate any other flags the deterministic seam passes through.
    p.parse_known_args(argv)

    print(json.dumps({
        "algorithm": ALGO,
        "error": "agent-optimize is agent-driven and has no deterministic loop.",
        "fix": "set `orchestration_mode: agent` in capevolve.yaml. In agent mode "
               "`cap-evolve run` does check+baseline then hands the loop to the "
               "conversational agent, which follows this skill's 'Agent-mode loop'. "
               "For a deterministic run choose hill-climb | gepa | skillopt instead.",
    }, indent=2))
    return 2


if __name__ == "__main__":
    sys.exit(main())
