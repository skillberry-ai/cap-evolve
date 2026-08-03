"""Generic observer protocol for cap-evolve run events.

The observer subsystem lets external platforms (MLflow, OpenTelemetry, custom
dashboards, …) receive the same events that ``RunDir.log_event`` writes to the
local ``events.jsonl``.  Observers are deliberately *fire-and-forget*: a failure
in any observer must never block or crash an optimization run.

Quick start
-----------

1. Subclass :class:`RunObserver` and implement :meth:`on_event` (and optionally
   :meth:`on_run_start` / :meth:`on_run_end`).
2. Attach the observer to a :class:`~cap_evolve.rundir.RunDir` via
   ``run_dir.add_observer(my_observer)`` before the loop begins.
3. Events flow automatically — ``log_event`` fans out to every attached observer.

Batteries included
------------------

* :class:`NullObserver` — the default; silently discards every event.
* :class:`CompositeObserver` — fan-out: wraps N children so the caller only
  manages one handle.
* :func:`observer_from_config` — instantiate an observer from a simple dict
  ``{"backend": "mlflow", ...}`` (entry-point based, so third-party backends
  can register themselves).
"""

from __future__ import annotations

import importlib
import logging
import sys
from typing import Any, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)

# ---- abstract base --------------------------------------------------------

class RunObserver:
    """Abstract observer that receives cap-evolve run events.

    Subclass this and override the ``on_*`` hooks you care about.  Every hook
    has a no-op default so you only override what you need.

    **Contract:** implementations must be safe to call from the hot loop.
    Raise nothing (log instead), and keep work O(1) or defer it to a thread.
    """

    def on_run_start(self, run_id: str, metadata: Dict[str, Any]) -> None:
        """Called once when the optimisation run begins.

        *metadata* contains budget, spec-file info, etc.
        """

    def on_event(self, event: Dict[str, Any]) -> None:
        """Called for every ``RunDir.log_event`` invocation.

        *event* is the full dict (``kind``, ``t``, plus all fields).
        """

    def on_run_end(self, summary: Dict[str, Any]) -> None:
        """Called once when the run finishes (successfully or not).

        *summary* contains final metrics, test reward, etc.
        """

    def flush(self) -> None:
        """Flush any buffered data.  Called at run end / on SIGINT."""

    def close(self) -> None:
        """Release resources (network connections, file handles)."""


# ---- null (default) -------------------------------------------------------

class NullObserver(RunObserver):
    """No-op observer — the default when no external backend is configured."""


# ---- composite ------------------------------------------------------------

class CompositeObserver(RunObserver):
    """Fan-out observer that delegates to N children.

    Exceptions in any child are caught and logged so one broken backend cannot
    take down the others (or the run).
    """

    def __init__(self, children: Sequence[RunObserver] | None = None) -> None:
        self._children: List[RunObserver] = list(children or [])

    def add(self, observer: RunObserver) -> None:
        self._children.append(observer)

    @property
    def children(self) -> List[RunObserver]:
        return list(self._children)

    # -- delegating hooks ----------------------------------------------------

    def on_run_start(self, run_id: str, metadata: Dict[str, Any]) -> None:
        for c in self._children:
            try:
                c.on_run_start(run_id, metadata)
            except Exception:
                log.warning("observer %s.on_run_start failed", type(c).__name__, exc_info=True)

    def on_event(self, event: Dict[str, Any]) -> None:
        for c in self._children:
            try:
                c.on_event(event)
            except Exception:
                log.warning("observer %s.on_event failed", type(c).__name__, exc_info=True)

    def on_run_end(self, summary: Dict[str, Any]) -> None:
        for c in self._children:
            try:
                c.on_run_end(summary)
            except Exception:
                log.warning("observer %s.on_run_end failed", type(c).__name__, exc_info=True)

    def flush(self) -> None:
        for c in self._children:
            try:
                c.flush()
            except Exception:
                log.warning("observer %s.flush failed", type(c).__name__, exc_info=True)

    def close(self) -> None:
        for c in self._children:
            try:
                c.close()
            except Exception:
                log.warning("observer %s.close failed", type(c).__name__, exc_info=True)


# ---- factory ---------------------------------------------------------------

# Built-in backend aliases → dotted class paths.  Third-party packages can
# register via the ``capevolve.observers`` entry-point group.
_BUILTIN_BACKENDS: Dict[str, str] = {
    "null": "cap_evolve.observers:NullObserver",
    "mlflow": "cap_evolve.observers_mlflow:MLflowObserver",
    "otel": "cap_evolve.observers_otel:OTelObserver",
    "opentelemetry": "cap_evolve.observers_otel:OTelObserver",
}


def _import_class(dotted: str) -> type:
    """Import ``'pkg.mod:ClassName'`` and return the class object."""
    module_path, _, class_name = dotted.rpartition(":")
    if not module_path or not class_name:
        raise ValueError(f"Expected 'module:ClassName', got {dotted!r}")
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _resolve_backend(name: str) -> type:
    """Resolve a backend name to a concrete RunObserver subclass.

    Resolution order:
    1. Built-in alias (``_BUILTIN_BACKENDS``).
    2. ``capevolve.observers`` entry-point group (if ``importlib.metadata``
       is available — it always is on Python ≥ 3.10).
    3. Treat *name* itself as a ``module:Class`` dotted path.
    """
    # 1. builtin
    if name in _BUILTIN_BACKENDS:
        return _import_class(_BUILTIN_BACKENDS[name])

    # 2. entry-points
    try:
        if sys.version_info >= (3, 12):
            from importlib.metadata import entry_points
            eps = entry_points(group="capevolve.observers", name=name)
        else:
            from importlib.metadata import entry_points
            all_eps = entry_points()
            if isinstance(all_eps, dict):
                eps = [e for e in all_eps.get("capevolve.observers", []) if e.name == name]
            else:
                eps = all_eps.select(group="capevolve.observers", name=name)  # type: ignore[union-attr]
        for ep in eps:
            return ep.load()
    except Exception:
        pass

    # 3. dotted path
    if ":" in name:
        return _import_class(name)

    raise ValueError(
        f"Unknown observer backend {name!r}. "
        f"Built-in backends: {sorted(_BUILTIN_BACKENDS)}. "
        f"Or pass 'module:ClassName' for a custom backend."
    )


def observer_from_config(cfg: Dict[str, Any]) -> RunObserver:
    """Instantiate a single :class:`RunObserver` from a config dict.

    The dict must contain a ``"backend"`` key (e.g. ``"mlflow"``).  Remaining
    keys are forwarded as ``**kwargs`` to the observer's ``__init__``.

    Example::

        observer_from_config({"backend": "mlflow", "experiment_name": "my-run"})
    """
    cfg = dict(cfg)  # don't mutate caller's dict
    backend_name = cfg.pop("backend", None)
    if not backend_name:
        raise ValueError("Observer config must include a 'backend' key")
    cls = _resolve_backend(backend_name)
    return cls(**cfg)


def observers_from_config(
    configs: Optional[Sequence[Dict[str, Any]]],
) -> RunObserver:
    """Build a (possibly composite) observer from a list of config dicts.

    Returns :class:`NullObserver` when *configs* is ``None`` or empty.
    """
    if not configs:
        return NullObserver()
    observers = [observer_from_config(c) for c in configs]
    if len(observers) == 1:
        return observers[0]
    return CompositeObserver(observers)
