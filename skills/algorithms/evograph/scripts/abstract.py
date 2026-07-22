"""evograph carries no per-skill abstract methods.

Like the other algorithm skills, it composes the project adapter contract
(tasks/run_target/score) via cap-evolve's primitives. evograph is AGENT MODE ONLY:
its loop is prose the coding agent runs (see SKILL.md "Step 2 — Round loop"), not a
deterministic engine — so there is no policy to materialize here.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_POLICY: dict = {}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    return {}
