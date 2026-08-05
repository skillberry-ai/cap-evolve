"""Test observer config parsing and factory."""

from __future__ import annotations

from capevolve_telemetry.config import load_observers, load_observers_from_state


def test_empty_config_returns_no_observers():
    assert load_observers([]) == []
    assert load_observers(None) == []


def test_none_states_returns_no_observers():
    assert load_observers_from_state(None) == []
    assert load_observers_from_state([]) == []


def test_unknown_backend_skipped():
    result = load_observers([{"backend": "datadog"}])
    assert result == []


def test_unknown_backend_skipped_from_state():
    result = load_observers_from_state([{"backend": "datadog"}])
    assert result == []
