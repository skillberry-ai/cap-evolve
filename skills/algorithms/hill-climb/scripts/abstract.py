"""hill-climb has no per-skill abstract methods beyond the project adapter.

It composes the contract methods (tasks/run_target/score/materialize) via the
shared harness; the optimizer skill supplies the proposer and the capability
skill owns the editable surface. Nothing here needs filling, so ``check.py``
verifies the loop wiring + the focus schedule rather than implementations.
"""

from __future__ import annotations

from pathlib import Path

# A focus schedule is the only "policy" this algorithm carries; the default is
# "all" (propose against the whole train set each iteration).
DEFAULT_POLICY = {"focus": "all"}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    return {}
