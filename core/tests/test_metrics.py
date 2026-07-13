"""Shown-only secondary metrics ride alongside the gating primary reward."""
import pytest
from cap_evolve.types import Score


def _score(**kw):
    return Score(task_id="t1", reward=0.8, **kw)


def test_empty_metrics_is_allowed_and_roundtrips():
    s = _score()
    assert s.metrics == []
    assert s.primary_metric() is None
    assert Score.from_dict(s.to_dict()).metrics == []


def test_primary_metric_returned():
    s = _score(metrics=[
        {"name": "acc", "value": 0.8, "primary": True, "direction": "higher"},
        {"name": "latency_ms", "value": 120.0, "primary": False, "direction": "lower"},
    ])
    assert s.primary_metric()["name"] == "acc"
    assert [m["name"] for m in s.metrics if not m["primary"]] == ["latency_ms"]


def test_roundtrip_preserves_metrics():
    s = _score(metrics=[{"name": "acc", "value": 0.8, "primary": True, "direction": "higher"}])
    assert Score.from_dict(s.to_dict()).metrics == s.metrics


def test_exactly_one_primary_required():
    with pytest.raises(ValueError):
        _score(metrics=[
            {"name": "a", "value": 0.8, "primary": True, "direction": "higher"},
            {"name": "b", "value": 0.8, "primary": True, "direction": "higher"},
        ])
    with pytest.raises(ValueError):
        _score(metrics=[{"name": "a", "value": 0.8, "primary": False, "direction": "higher"}])


def test_direction_must_be_higher_or_lower():
    with pytest.raises(ValueError):
        _score(metrics=[{"name": "a", "value": 0.8, "primary": True, "direction": "sideways"}])


def test_primary_value_must_match_reward():
    with pytest.raises(ValueError):
        _score(metrics=[{"name": "a", "value": 0.5, "primary": True, "direction": "higher"}])
