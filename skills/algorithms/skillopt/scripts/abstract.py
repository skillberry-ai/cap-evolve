"""skillopt has no per-skill abstract methods beyond the project adapter.

Like hill-climb, it composes the contract methods (tasks/run_target/score/
materialize) via the shared harness; the optimizer skill supplies the proposer
and the capability skill owns the editable surface. The only "policy" this
algorithm carries is its schedule defaults (the textual learning rate), so
``check.py`` verifies the epoch/step loop + schedule + buffer + gated slow-update
behaviorally rather than asserting an implementation here.
"""

from __future__ import annotations

from pathlib import Path

# Defaults for the textual learning rate (integer edit budget) and the loop shape.
DEFAULT_POLICY = {
    "epochs": 4,
    "edit_budget": 4,
    "min_edit_budget": 2,
    "lr_schedule": "cosine",
    "slow_update": True,
}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    return {}
