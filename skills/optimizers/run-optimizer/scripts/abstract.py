"""run-optimizer has no capability artifact to materialize.

An *optimizer* drives edits; it does not own an editable capability surface (that
is what the ``capabilities/*`` skills do). The manifest still expects every skill
to name an ``abstract`` module, so this one documents that there is nothing to
materialize and exposes the registry it resolves against, which is the only
"surface" an optimizer skill has.
"""

from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.specfile import read_yaml

# Optimizers do not edit a capability; there is no per-candidate materialize step.
DEFAULT_POLICY: dict = {}


def registry() -> dict:
    """Return the parsed optimizer registry (name -> row)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "registry.yaml"
        if cand.exists() and parent.name == "optimizers":
            return read_yaml(cand.read_text(encoding="utf-8"))
    return {}


def materialize(capability_dir: Path) -> dict:  # noqa: ARG001
    """No-op: an optimizer skill has no capability components to flatten."""
    return {}
