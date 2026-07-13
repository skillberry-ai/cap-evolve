"""Secondary metrics survive aggregation/serialization for display."""
import json

from cap_evolve.loop import aggregate_scores
from cap_evolve.harness import _aggregate_metrics, split_result_from_rollouts
from cap_evolve.rundir import RunDir
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


def test_aggregate_metrics_pins_primary_to_reward():
    per_trial = [
        [{"name": "acc", "value": 1.0, "primary": True, "direction": "higher"},
         {"name": "latency_ms", "value": 100.0, "primary": False, "direction": "lower"}],
        [{"name": "acc", "value": 0.0, "primary": True, "direction": "higher"},
         {"name": "latency_ms", "value": 200.0, "primary": False, "direction": "lower"}],
    ]
    out = _aggregate_metrics(per_trial, reduced_reward=0.5)
    by = {m["name"]: m for m in out}
    assert by["acc"]["value"] == 0.5          # primary pinned to reduced reward
    assert by["acc"]["primary"] is True
    assert by["latency_ms"]["value"] == 150.0  # secondary averaged
    assert by["latency_ms"]["direction"] == "lower"


def test_aggregate_metrics_empty():
    assert _aggregate_metrics([[], []], 0.7) == []


def test_reduced_score_carries_metrics():
    per_trial = [[{"name": "acc", "value": 1.0, "primary": True, "direction": "higher"}],
                 [{"name": "acc", "value": 0.0, "primary": True, "direction": "higher"}]]
    reward = 0.5
    s = Score(task_id="t1", reward=reward, trial_rewards=[1.0, 0.0],
              metrics=_aggregate_metrics(per_trial, reward))
    assert s.primary_metric()["value"] == 0.5   # no ValueError raised
    assert s.to_dict()["metrics"][0]["name"] == "acc"


def test_split_result_from_rollouts_carries_metrics(tmp_path):
    # Reduction path the dashboard uses: two persisted trials for one task, each
    # with a primary metric whose value differs per trial. The reconstructed
    # per-task Score must carry metrics with the primary pinned to the mean reward.
    run_dir = RunDir.create(tmp_path)
    val_dir = run_dir.rollouts / "val"
    val_dir.mkdir(parents=True, exist_ok=True)
    trials = [
        (1.0, [{"name": "acc", "value": 1.0, "primary": True, "direction": "higher"},
               {"name": "latency_ms", "value": 100.0, "primary": False, "direction": "lower"}]),
        (0.0, [{"name": "acc", "value": 0.0, "primary": True, "direction": "higher"},
               {"name": "latency_ms", "value": 200.0, "primary": False, "direction": "lower"}]),
    ]
    for k, (reward, metrics) in enumerate(trials):
        score = Score(task_id="t1", reward=reward, trial_rewards=[reward], metrics=metrics)
        (val_dir / f"t1__cand__t{k}.json").write_text(
            json.dumps({"input": {}, "rollout": {}, "score": score.to_dict()}, default=str),
            encoding="utf-8",
        )
    result = split_result_from_rollouts(run_dir, tag="cand", split="val")
    row = result.to_dict()["per_task"][0]
    by = {m["name"]: m for m in row["metrics"]}
    assert by["acc"]["value"] == 0.5          # primary pinned to mean reward
    assert by["acc"]["primary"] is True
    assert by["latency_ms"]["value"] == 150.0  # secondary averaged
