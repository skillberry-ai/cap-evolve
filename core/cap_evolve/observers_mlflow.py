"""MLflow observer for cap-evolve.

Logs per-iteration metrics, parameters, and run summaries to an MLflow tracking
server.  Requires the ``mlflow`` package (``pip install mlflow``).

Usage::

    from cap_evolve.observers_mlflow import MLflowObserver

    obs = MLflowObserver(experiment_name="cap-evolve/my-project")
    run_dir.add_observer(obs)

Or via config::

    observer_from_config({
        "backend": "mlflow",
        "experiment_name": "cap-evolve/my-project",
        "tracking_uri": "http://localhost:5000",
    })
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .observers import RunObserver

log = logging.getLogger(__name__)

# Numeric event fields that should be logged as MLflow metrics.
_METRIC_FIELDS = frozenset({
    "reward", "stderr", "val", "parent_val", "cost_usd",
    "tokens", "seconds", "optimizer_seconds", "runner_seconds",
    "train", "test", "iterations", "metric_calls", "usd",
    "test_reward", "test_stderr",
})


class MLflowObserver(RunObserver):
    """Push cap-evolve events to MLflow Tracking.

    Parameters
    ----------
    experiment_name : str
        MLflow experiment name (created if it doesn't exist).
    tracking_uri : str or None
        MLflow tracking URI.  ``None`` uses the ``MLFLOW_TRACKING_URI``
        environment variable or the default local ``./mlruns``.
    run_name : str or None
        Optional human-readable run name.
    tags : dict or None
        Extra tags to set on the MLflow run.
    """

    def __init__(
        self,
        experiment_name: str = "cap-evolve",
        tracking_uri: Optional[str] = None,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        self._experiment_name = experiment_name
        self._tracking_uri = tracking_uri
        self._run_name = run_name
        self._tags = dict(tags or {})
        self._mlflow: Any = None  # lazy import
        self._run: Any = None
        self._step = 0

    # -- lazy init -----------------------------------------------------------

    def _ensure_mlflow(self) -> Any:
        if self._mlflow is not None:
            return self._mlflow
        try:
            import mlflow  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "MLflowObserver requires the 'mlflow' package.  "
                "Install it with:  pip install mlflow"
            ) from exc
        if self._tracking_uri:
            mlflow.set_tracking_uri(self._tracking_uri)
        mlflow.set_experiment(self._experiment_name)
        self._mlflow = mlflow
        return mlflow

    # -- hooks ---------------------------------------------------------------

    def on_run_start(self, run_id: str, metadata: Dict[str, Any]) -> None:
        try:
            mlflow = self._ensure_mlflow()
            self._run = mlflow.start_run(run_name=self._run_name or run_id)
            tags = {"capevolve.run_id": run_id, **self._tags}
            mlflow.set_tags(tags)
            # Log budget as params
            budget = metadata.get("budget", {})
            if budget:
                mlflow.log_params({f"budget.{k}": str(v) for k, v in budget.items()})
        except Exception:
            log.warning("MLflowObserver.on_run_start failed", exc_info=True)

    def on_event(self, event: Dict[str, Any]) -> None:
        try:
            mlflow = self._ensure_mlflow()
            if self._run is None:
                self._run = mlflow.start_run(run_name=self._run_name)
            kind = event.get("kind", "unknown")
            metrics = {}
            for key, val in event.items():
                if key in _METRIC_FIELDS and isinstance(val, (int, float)):
                    metrics[f"{kind}.{key}"] = val
            if metrics:
                mlflow.log_metrics(metrics, step=self._step)
            self._step += 1
        except Exception:
            log.warning("MLflowObserver.on_event failed", exc_info=True)

    def on_run_end(self, summary: Dict[str, Any]) -> None:
        try:
            mlflow = self._ensure_mlflow()
            # Log final summary metrics
            final_metrics = {}
            for key, val in summary.items():
                if isinstance(val, (int, float)):
                    final_metrics[f"final.{key}"] = val
            if final_metrics:
                mlflow.log_metrics(final_metrics)
            mlflow.end_run()
            self._run = None
        except Exception:
            log.warning("MLflowObserver.on_run_end failed", exc_info=True)

    def flush(self) -> None:
        pass  # MLflow client flushes on each call

    def close(self) -> None:
        try:
            if self._run is not None and self._mlflow is not None:
                self._mlflow.end_run()
                self._run = None
        except Exception:
            log.warning("MLflowObserver.close failed", exc_info=True)
