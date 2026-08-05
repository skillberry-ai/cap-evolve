"""Observer protocol for external telemetry integrations.

Pure stdlib. Observer backends (MLflow, OTel) live in ``capevolve_telemetry``
and satisfy this protocol structurally -- they never import or subclass it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RunObserver(Protocol):
    """Receives every event dispatched by ``RunDir.log_event``.

    Implementations may be stateful (e.g. holding an MLflow run_id).
    ``on_event`` is called synchronously after the event is persisted to
    ``events.jsonl`` -- an observer crash must not break the run, so
    ``RunDir`` wraps each call in a ``try/except``.

    ``state()`` returns serialisable state (e.g. run_id, trace_id) that
    ``RunDir`` persists so a subsequent subprocess can reconstruct the
    observer via the backend's ``from_state`` class-method.

    ``close()`` is called when the phase ends to flush pending data.
    """

    def on_event(self, kind: str, event: dict[str, Any]) -> None: ...
    def state(self) -> dict[str, Any]: ...
    def close(self) -> None: ...
