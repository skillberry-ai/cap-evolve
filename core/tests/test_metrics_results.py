"""Secondary metrics survive aggregation/serialization for display."""
from cap_evolve.loop import aggregate_scores
from cap_evolve.types import Score


def test_score_dict_includes_secondaries():
    s = Score(task_id="t1", reward=0.8, metrics=[
        {"name": "acc", "value": 0.8, "primary": True, "direction": "higher"},
        {"name": "latency_ms", "value": 120.0, "primary": False, "direction": "lower"},
    ])
    d = s.to_dict()
    assert d["metrics"][1]["name"] == "latency_ms"
    # display-only: reward (the gate scalar) is unchanged by the presence of secondaries
    assert d["reward"] == 0.8


def test_aggregate_scores_preserves_metrics():
    # Guard: the aggregation site (loop.aggregate_scores) emits per-task rows via
    # Score.to_dict(), so the shown-only `metrics` catalog reaches the results JSON
    # verbatim. Display-only: the aggregate gate scalar `reward` is unaffected.
    scores = [
        Score(task_id="t1", reward=0.8, metrics=[
            {"name": "acc", "value": 0.8, "primary": True, "direction": "higher"},
            {"name": "latency_ms", "value": 120.0, "primary": False, "direction": "lower"},
        ]),
        Score(task_id="t2", reward=0.4, metrics=[
            {"name": "acc", "value": 0.4, "primary": True, "direction": "higher"},
            {"name": "latency_ms", "value": 90.0, "primary": False, "direction": "lower"},
        ]),
    ]
    result = aggregate_scores("val", scores)
    per_task = result.to_dict()["per_task"]
    assert per_task[0]["metrics"][1]["name"] == "latency_ms"
    assert per_task[1]["metrics"][1]["value"] == 90.0
    # gate scalar reward on each row is the primary value, unchanged
    assert per_task[0]["reward"] == 0.8
    assert per_task[1]["reward"] == 0.4
