"""OpenTelemetry observer backend.

Maps the cap-evolve run to an OTel trace:

* The entire optimisation run is one trace (``trace_id`` persisted across phases).
* Each ``step``/``baseline``/``finalize``/``evaluate`` event becomes a span,
  with duration reconstructed from timing fields in the event payload.
* Minor events are recorded as span-events on the current phase span.

When ``mlflow_tracking_uri`` is set, spans are exported via OTLP HTTP to
MLflow's ``/v1/traces`` endpoint so they appear in MLflow's Traces tab
alongside the metrics logged by ``MlflowObserver``.
"""

from __future__ import annotations

from typing import Any


class OtelObserver:
    """Exports cap-evolve events as OpenTelemetry spans."""

    def __init__(
        self,
        *,
        trace_id: str | None = None,
        phase_span_id: str | None = None,
        endpoint: str = "",
        service_name: str = "cap-evolve",
        experiment_id: str = "",
        mlflow_run_id: str = "",
    ):
        self._trace_id = trace_id
        self._phase_span_id = phase_span_id
        self._endpoint = endpoint
        self._service_name = service_name
        self._experiment_id = experiment_id
        self._mlflow_run_id = mlflow_run_id
        self._tracer = None
        self._phase_span = None
        self._setup_done = False

    # ---- lazy setup --------------------------------------------------------

    def _setup(self) -> None:
        if self._setup_done:
            return
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        res_attrs: dict[str, str] = {"service.name": self._service_name}
        if self._mlflow_run_id:
            res_attrs["mlflow.source.run_id"] = self._mlflow_run_id
        resource = Resource.create(res_attrs)
        provider = TracerProvider(resource=resource)

        if self._endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            headers = {}
            if self._experiment_id:
                headers["x-mlflow-experiment-id"] = self._experiment_id

            exporter = OTLPSpanExporter(
                endpoint=self._endpoint,
                headers=headers or None,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))

        # Global override — safe in cap-evolve's subprocess-per-phase model
        # but would conflict with a host app that already configured OTel.
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("capevolve")
        self._setup_done = True

    # ---- construction ------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        run_dir_root: str = "",
        run_name: str = "",
        mlflow_run_id: str = "",
    ) -> "OtelObserver":
        endpoint = str(config.get("endpoint", ""))
        experiment_id = str(config.get("experiment_id", ""))
        mlflow_tracking_uri = str(config.get("mlflow_tracking_uri", ""))

        if mlflow_tracking_uri and not endpoint:
            endpoint = mlflow_tracking_uri.rstrip("/") + "/v1/traces"

        if mlflow_tracking_uri and not experiment_id:
            experiment_id = _resolve_mlflow_experiment_id(
                mlflow_tracking_uri,
                str(config.get("experiment_name", "cap-evolve")),
            )

        obs = cls(
            endpoint=endpoint,
            service_name=str(config.get("service_name", "cap-evolve")),
            experiment_id=experiment_id,
            mlflow_run_id=mlflow_run_id,
        )
        obs._setup()
        obs._phase_span = obs._tracer.start_span(
            f"cap-evolve-run:{run_name or run_dir_root}",
            attributes={"run_dir": run_dir_root},
        )
        ctx = obs._phase_span.get_span_context()
        obs._trace_id = format(ctx.trace_id, "032x")
        obs._phase_span_id = format(ctx.span_id, "016x")
        return obs

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "OtelObserver":
        obs = cls(
            trace_id=state.get("trace_id"),
            phase_span_id=state.get("phase_span_id"),
            endpoint=state.get("endpoint", ""),
            service_name=state.get("service_name", "cap-evolve"),
            experiment_id=state.get("experiment_id", ""),
            mlflow_run_id=state.get("mlflow_run_id", ""),
        )
        obs._setup()
        return obs

    # ---- protocol ----------------------------------------------------------

    def on_event(self, kind: str, event: dict[str, Any]) -> None:
        self._setup()
        import time as _time

        t = float(event.get("t", _time.time()))
        t_ns = int(t * 1e9)

        _SPAN_KINDS = {
            "step": "runner_seconds",
            "baseline": None,
            "finalize": None,
            "evaluate": "seconds",
        }

        if kind in _SPAN_KINDS:
            attrs: dict[str, Any] = {}
            if self._mlflow_run_id:
                attrs["mlflow.source.run_id"] = self._mlflow_run_id
            for k, v in event.items():
                if k == "t":
                    continue
                if isinstance(v, (str, int, float, bool)):
                    attrs[f"capevolve.{k}"] = v

            duration_key = _SPAN_KINDS[kind]
            duration_s = float(event.get(duration_key, 0)) if duration_key else 0
            start_ns = t_ns - int(duration_s * 1e9) if duration_s else t_ns

            span = self._tracer.start_span(
                f"capevolve.{kind}",
                start_time=start_ns,
                attributes=attrs,
            )
            span.end(end_time=t_ns)
        else:
            if self._phase_span and self._phase_span.is_recording():
                attrs = {}
                for k, v in event.items():
                    if k == "t":
                        continue
                    if isinstance(v, (str, int, float, bool)):
                        attrs[f"capevolve.{k}"] = v
                self._phase_span.add_event(
                    f"capevolve.{kind}", attributes=attrs, timestamp=t_ns
                )

    def state(self) -> dict[str, Any]:
        return {
            "backend": "otel",
            "trace_id": self._trace_id,
            "phase_span_id": self._phase_span_id,
            "endpoint": self._endpoint,
            "service_name": self._service_name,
            "experiment_id": self._experiment_id,
            "mlflow_run_id": self._mlflow_run_id,
        }

    def close(self) -> None:
        if self._phase_span and hasattr(self._phase_span, "end"):
            try:
                self._phase_span.end()
            except Exception:  # noqa: BLE001
                pass
        if self._setup_done:
            try:
                from opentelemetry import trace

                provider = trace.get_tracer_provider()
                if hasattr(provider, "force_flush"):
                    provider.force_flush()
            except Exception:  # noqa: BLE001
                pass


def _resolve_mlflow_experiment_id(tracking_uri: str, experiment_name: str) -> str:
    """Look up the MLflow experiment ID by name, creating it if needed."""
    try:
        import mlflow

        client = mlflow.MlflowClient(tracking_uri)
        exp = client.get_experiment_by_name(experiment_name)
        if exp is not None:
            return exp.experiment_id
        return client.create_experiment(experiment_name)
    except Exception:  # noqa: BLE001
        return ""
