"""Observer factory -- reads capevolve.yaml config and builds observer instances.

Config schema in ``capevolve.yaml``::

    observers:
      - backend: mlflow
        tracking_uri: http://localhost:5000
        experiment_name: cap-evolve
      - backend: otel
        mlflow_tracking_uri: http://localhost:5000
        experiment_name: cap-evolve
        service_name: cap-evolve-engine

When the ``otel`` backend has ``mlflow_tracking_uri`` set, the endpoint is
auto-derived as ``<tracking_uri>/v1/traces`` and the experiment ID is resolved
by name, so traces appear in MLflow's Traces tab alongside the metrics.
"""

from __future__ import annotations

from typing import Any


def load_observers(
    config: list[dict[str, Any]] | None,
    *,
    run_dir_root: str = "",
    run_name: str = "",
    run_tags: dict[str, str] | None = None,
) -> list:
    """Instantiate observers from the parsed ``capevolve.yaml`` observers list."""
    observers: list = []
    mlflow_run_id = ""
    for entry in config or []:
        backend = str(entry.get("backend", "")).strip().lower()
        if backend == "mlflow":
            from .mlflow_observer import MlflowObserver

            obs = MlflowObserver.from_config(
                entry, run_dir_root=run_dir_root, run_name=run_name,
                run_tags=run_tags,
            )
            mlflow_run_id = obs.run_id
            observers.append(obs)
        elif backend == "otel":
            from .otel_observer import OtelObserver

            observers.append(
                OtelObserver.from_config(
                    entry, run_dir_root=run_dir_root, run_name=run_name,
                    mlflow_run_id=mlflow_run_id,
                )
            )
    return observers


def load_observers_from_state(states: list[dict[str, Any]] | None) -> list:
    """Reconstruct observers from persisted state (cross-process resume)."""
    observers: list = []
    for s in states or []:
        backend = str(s.get("backend", "")).strip().lower()
        if backend == "mlflow":
            from .mlflow_observer import MlflowObserver

            observers.append(MlflowObserver.from_state(s))
        elif backend == "otel":
            from .otel_observer import OtelObserver

            observers.append(OtelObserver.from_state(s))
    return observers
