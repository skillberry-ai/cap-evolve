"""Dynamic, cost-aware model routing (issue #665, workstream 5).

``capevolve.yaml`` has one spec-wide ``optimizer_model`` for every optimizer-driven
decision — cheap mechanical steps (clustering/classification) and expensive judgment
steps (root-cause analysis, merge-conflict reasoning) all get the same model. This
module adds an optional per-role override, ``model_routing``, without changing
behavior for any config that doesn't set it:

    model_routing:
      root_cause: claude-opus-4
      propose: claude-opus-4
      implement: claude-haiku-4   # cheap mechanical edit application

:func:`resolve_model` is the one fallback chain every call site should use instead of
reading ``optimizer_model`` directly. :class:`ModelSelection` + :func:`record_model_selection`
log the resulting role->model decision to the run's existing ``events.jsonl`` (via
``RunDir.log_event``) — no parallel telemetry path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

#: Decision roles ``model_routing`` may override, per issue #665 ws5's data model.
ROLES = ("plan", "root_cause", "propose", "implement", "evaluation_analysis", "merge", "synthesis")


class ModelRoutingError(ValueError):
    """Raised by :func:`resolve_model` when a role has no model configured anywhere."""


def resolve_model(role: str, spec: dict) -> str:
    """Resolve the model id to use for ``role``.

    Fallback chain: explicit ``model_routing.<role>`` override -> spec-wide
    ``optimizer_model`` default -> :class:`ModelRoutingError` if neither is set.

    Backward compatible by construction: a spec with no ``model_routing`` block (every
    config today) always resolves every role to ``optimizer_model`` — identical to the
    pre-routing behavior at every call site.
    """
    routing = spec.get("model_routing")
    override = routing.get(role) if isinstance(routing, dict) else None
    if override:
        return str(override)
    default = spec.get("optimizer_model")
    if default:
        return str(default)
    raise ModelRoutingError(
        f"no model configured for role {role!r}: set model_routing.{role} or optimizer_model")


@dataclass
class ModelSelection:
    """One role -> model routing decision, as persisted to ``events.jsonl``."""

    role: str
    model: str
    rationale: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_event_fields(self) -> dict:
        d: dict = {"role": self.role, "model": self.model, "timestamp": self.timestamp}
        if self.rationale:
            d["rationale"] = self.rationale
        return d


def record_model_selection(run_dir, role: str, model: str, rationale: str | None = None) -> None:
    """Append a :class:`ModelSelection` to the run via ``run_dir.log_event``.

    Reuses the existing audit-log mechanism (``RunDir.log_event`` -> ``events.jsonl`` +
    observer fan-out) rather than inventing a second logging path.
    """
    sel = ModelSelection(role=role, model=model, rationale=rationale)
    run_dir.log_event("model_selection", **sel.to_event_fields())
