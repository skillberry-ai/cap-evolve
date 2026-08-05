"""Test OtelObserver event mapping without a real OTel collector."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from capevolve_telemetry.otel_observer import OtelObserver


def _make_observer(**overrides) -> OtelObserver:
    obs = OtelObserver(
        endpoint=overrides.get("endpoint", ""),
        service_name=overrides.get("service_name", "test-service"),
        experiment_id=overrides.get("experiment_id", ""),
    )
    obs._tracer = MagicMock()
    obs._setup_done = True

    mock_span = MagicMock()
    mock_span.is_recording.return_value = True
    mock_ctx = MagicMock()
    mock_ctx.trace_id = 0xDEADBEEF
    mock_ctx.span_id = 0xCAFE0001
    mock_span.get_span_context.return_value = mock_ctx
    obs._phase_span = mock_span

    obs._tracer.start_span.return_value = MagicMock()
    return obs


def test_step_event_creates_span():
    obs = _make_observer()
    obs.on_event("step", {"t": time.time(), "kind": "step",
                           "val": 0.85, "runner_seconds": 30.0})
    obs._tracer.start_span.assert_called_once()
    span = obs._tracer.start_span.return_value
    span.end.assert_called_once()


def test_baseline_event_creates_span():
    obs = _make_observer()
    obs.on_event("baseline", {"t": time.time(), "kind": "baseline", "val": 0.5})
    obs._tracer.start_span.assert_called_once()


def test_minor_event_becomes_span_event():
    obs = _make_observer()
    obs.on_event("budget_warning", {"t": time.time(), "kind": "budget_warning",
                                     "metric": "usd", "pct": 80})
    obs._phase_span.add_event.assert_called_once()
    call_args = obs._phase_span.add_event.call_args
    assert "capevolve.budget_warning" in call_args[0]


def test_state_round_trip():
    obs = OtelObserver(
        trace_id="deadbeef",
        phase_span_id="cafe0001",
        endpoint="http://localhost:5000/v1/traces",
        service_name="test-svc",
        experiment_id="42",
    )
    s = obs.state()
    assert s["backend"] == "otel"
    assert s["trace_id"] == "deadbeef"
    assert s["endpoint"] == "http://localhost:5000/v1/traces"
    assert s["experiment_id"] == "42"

    restored = OtelObserver.from_state(s)
    assert restored._experiment_id == "42"
    assert restored._endpoint == "http://localhost:5000/v1/traces"


def test_close_ends_phase_span():
    obs = _make_observer()
    obs.close()
    obs._phase_span.end.assert_called_once()
