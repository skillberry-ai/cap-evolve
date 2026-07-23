"""OpenTelemetry observer for cap-evolve.

Emits cap-evolve events as OpenTelemetry spans and metrics, so runs are visible
in any OTel-compatible backend (Jaeger, Zipkin, Grafana Tempo, Honeycomb, …).

Requires the ``opentelemetry-api`` and ``opentelemetry-sdk`` packages::

    pip install opentelemetry-api opentelemetry-sdk

Usage::

    from cap_evolve.observers_otel import OTelObserver

    obs = OTelObserver(service_name="cap-evolve")
    run_dir.add_observer(obs)

Or via config::

    observer_from_config({
        "backend": "otel",
        "service_name": "cap-evolve",
    })
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .observers import RunObserver

log = logging.getLogger(__name__)


class OTelObserver(RunObserver):
    """Push cap-evolve events to an OpenTelemetry collector.

    Parameters
    ----------
    service_name : str
        The OTel service name (``service.name`` resource attribute).
    endpoint : str or None
        OTLP exporter endpoint.  ``None`` uses the ``OTEL_EXPORTER_OTLP_ENDPOINT``
        environment variable (default ``http://localhost:4317``).
    """

    def __init__(
        self,
        service_name: str = "cap-evolve",
        endpoint: Optional[str] = None,
    ) -> None:
        self._service_name = service_name
        self._endpoint = endpoint
        self._tracer: Any = None
        self._meter: Any = None
        self._run_span: Any = None
        self._event_counter: Any = None
        self._reward_gauge: Any = None

    # -- lazy init -----------------------------------------------------------

    def _ensure_otel(self) -> None:
        if self._tracer is not None:
            return
        try:
            from opentelemetry import trace, metrics  # type: ignore[import-untyped]
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-untyped]
            from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-untyped]
            from opentelemetry.sdk.resources import Resource  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "OTelObserver requires 'opentelemetry-api' and 'opentelemetry-sdk'.  "
                "Install with:  pip install opentelemetry-api opentelemetry-sdk"
            ) from exc

        resource = Resource.create({"service.name": self._service_name})

        # Traces
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("cap_evolve")

        # Metrics
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter("cap_evolve")

        self._event_counter = self._meter.create_counter(
            "capevolve.events",
            description="Total cap-evolve events emitted",
        )
        self._reward_gauge = self._meter.create_histogram(
            "capevolve.reward",
            description="Reward values observed during optimization",
        )

    # -- hooks ---------------------------------------------------------------

    def on_run_start(self, run_id: str, metadata: Dict[str, Any]) -> None:
        try:
            self._ensure_otel()
            self._run_span = self._tracer.start_span(
                "capevolve.run",
                attributes={"capevolve.run_id": run_id},
            )
        except Exception:
            log.warning("OTelObserver.on_run_start failed", exc_info=True)

    def on_event(self, event: Dict[str, Any]) -> None:
        try:
            self._ensure_otel()
            kind = event.get("kind", "unknown")

            # Record as a child span
            attrs = {"capevolve.event.kind": kind}
            for k, v in event.items():
                if isinstance(v, (str, int, float, bool)):
                    attrs[f"capevolve.{k}"] = v
            span = self._tracer.start_span(f"capevolve.event.{kind}", attributes=attrs)
            span.end()

            # Bump counter
            if self._event_counter:
                self._event_counter.add(1, {"kind": kind})

            # Record reward metric
            reward = event.get("reward") or event.get("val")
            if isinstance(reward, (int, float)) and self._reward_gauge:
                self._reward_gauge.record(reward, {"kind": kind})

        except Exception:
            log.warning("OTelObserver.on_event failed", exc_info=True)

    def on_run_end(self, summary: Dict[str, Any]) -> None:
        try:
            if self._run_span is not None:
                for k, v in summary.items():
                    if isinstance(v, (str, int, float, bool)):
                        self._run_span.set_attribute(f"capevolve.final.{k}", v)
                self._run_span.end()
                self._run_span = None
        except Exception:
            log.warning("OTelObserver.on_run_end failed", exc_info=True)

    def flush(self) -> None:
        pass  # OTel SDK manages its own export schedule

    def close(self) -> None:
        try:
            if self._run_span is not None:
                self._run_span.end()
                self._run_span = None
        except Exception:
            log.warning("OTelObserver.close failed", exc_info=True)
