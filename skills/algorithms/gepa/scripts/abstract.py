"""gepa has no per-skill abstract methods beyond the project adapter.

Like the other algorithm skills, it composes the adapter contract methods
(tasks/run_target/score/materialize) via the engine; the optimizer skill supplies
the proposer and the capability skill owns the editable surface. The only policy
this algorithm carries is its loop hyperparameters (minibatch size, component
selector, merge budget), which are CLI flags — so ``check.py`` verifies the loop
behaviour end-to-end rather than any implementation here.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_POLICY = {
    "minibatch_size": 4,
    "component_selector": "round_robin",
    "selection_strategy": "pareto_per_instance",
    "max_merges": 2,
}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    return {}
