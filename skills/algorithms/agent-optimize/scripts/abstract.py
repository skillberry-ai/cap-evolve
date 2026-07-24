"""agent-optimize has no per-skill abstract methods beyond the project adapter.

Like hill-climb, it composes the contract methods (tasks/run_target/score/
materialize) via the shared harness and the phase skills; there is no per-iteration
optimizer subprocess (the conversational agent *is* the optimizer in agent mode).
Nothing here needs filling, so ``check.py`` verifies the agent-mode contract
(the SKILL.md loop + honesty invariants + the deterministic-invocation guard)
rather than any implementation.
"""

from __future__ import annotations

from pathlib import Path

# This algorithm carries no tunable policy: the "policy" is the free-form loop
# in SKILL.md, bounded by the project's free-text stop_condition.
DEFAULT_POLICY: dict = {}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    return {}
