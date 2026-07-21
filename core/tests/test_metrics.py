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


def _ok_primary():
    return {"name": "acc", "value": 0.8, "primary": True, "direction": "higher"}


def test_secondary_value_must_be_numeric():
    # non-numeric value would crash later in _aggregate_metrics (float(m["value"]))
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(),
                        {"name": "note", "value": "fast", "primary": False, "direction": "lower"}])


def test_bool_value_rejected():
    # bool is a subclass of int but is not a metric value
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(),
                        {"name": "ok", "value": True, "primary": False, "direction": "higher"}])


def test_name_must_be_nonempty_string():
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(),
                        {"name": "", "value": 1.0, "primary": False, "direction": "lower"}])
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(),
                        {"name": None, "value": 1.0, "primary": False, "direction": "lower"}])


def test_duplicate_names_rejected():
    # names are used as dict keys during aggregation; duplicates silently collide
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(),
                        {"name": "acc", "value": 1.0, "primary": False, "direction": "higher"}])


def test_primary_must_be_bool():
    with pytest.raises(ValueError):
        _score(metrics=[{"name": "a", "value": 0.8, "primary": 1, "direction": "higher"}])


def test_non_dict_entry_rejected():
    with pytest.raises(ValueError):
        _score(metrics=[_ok_primary(), ["not", "a", "dict"]])
