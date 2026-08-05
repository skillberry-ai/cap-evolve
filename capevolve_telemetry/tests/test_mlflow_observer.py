"""Test MlflowObserver event mapping without a real MLflow server."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from capevolve_telemetry.mlflow_observer import MlflowObserver


def _make_observer(**kwargs) -> MlflowObserver:
    defaults = dict(run_id="test_run", tracking_uri="", experiment_name="test")
    defaults.update(kwargs)
    return MlflowObserver(**defaults)


def test_baseline_event_logs_metrics():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("baseline", {"t": time.time(), "kind": "baseline",
                               "val": 0.5, "stderr": 0.1})
    assert obs._client.log_metric.call_count == 2


def test_step_event_increments_counter():
    obs = _make_observer()
    obs._client = MagicMock()
    event = {
        "t": time.time(), "kind": "step",
        "candidate": "cand_0001", "accept": True,
        "val": 0.85, "parent_val": 0.80, "parent": "seed",
        "cost_usd": 1.5, "opt_cost_usd": 0.5,
        "optimizer_seconds": 10.0, "runner_seconds": 30.0,
        "tokens": 1000, "opt_tokens": 500,
    }
    obs.on_event("step", event)
    assert obs._step == 1
    assert obs._client.log_metric.call_count >= 5
    assert obs._client.set_tag.call_count >= 1


def test_step_counter_accumulates():
    obs = _make_observer()
    obs._client = MagicMock()
    for i in range(3):
        obs.on_event("step", {"t": time.time(), "kind": "step",
                               "val": 0.5 + i * 0.1, "parent_val": 0.5, "parent": "seed"})
    assert obs._step == 3


def test_finalize_event():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("finalize", {"t": time.time(), "kind": "finalize",
                               "test_reward": 0.9, "test_baseline_reward": 0.5,
                               "test_delta": 0.4, "best_id": "cand_0003"})
    assert obs._client.log_metric.call_count == 3
    obs._client.set_tag.assert_called_once()


def test_splits_logged_as_params():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("splits", {"t": time.time(), "kind": "splits",
                             "train": 10, "val": 5, "test": 5, "seed": 42})
    assert obs._client.log_param.call_count == 4


def test_evaluate_event():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("evaluate", {"t": time.time(), "kind": "evaluate",
                               "split": "val", "tag": "cand_0001",
                               "reward": 0.7, "stderr": 0.05,
                               "cost_usd": 0.5, "tokens": 200, "seconds": 5.0})
    assert obs._client.log_metric.call_count == 5


def test_state_round_trip():
    obs = _make_observer(step_counter=5)
    s = obs.state()
    assert s["backend"] == "mlflow"
    assert s["run_id"] == "test_run"
    assert s["step_counter"] == 5

    restored = MlflowObserver.from_state(s)
    assert restored._run_id == "test_run"
    assert restored._step == 5


def test_budget_warning():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("budget_warning", {"t": time.time(), "kind": "budget_warning",
                                     "metric": "usd", "pct": 80,
                                     "spent": 8.0, "limit": 10.0})
    obs._client.set_tag.assert_called_once()


def test_gepa_event_forwards_numeric_fields():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("gepa_select", {"t": time.time(), "kind": "gepa_select",
                                  "parent": "cand_0001", "strategy": "pareto",
                                  "sel_seed": 42, "pool": 3})
    assert obs._client.log_metric.call_count >= 1


def test_close_without_finalize_is_noop():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.close()
    obs._client.set_terminated.assert_not_called()


def test_close_after_finalize_terminates_run():
    obs = _make_observer()
    obs._client = MagicMock()
    obs.on_event("finalize", {"t": time.time(), "kind": "finalize",
                               "test_reward": 0.9, "best_id": "cand_0001"})
    obs.close()
    obs._client.set_terminated.assert_called_once_with("test_run")


def test_from_state_restores_created_at_ms():
    obs = MlflowObserver.from_state({
        "backend": "mlflow",
        "run_id": "test_run",
        "tracking_uri": "",
        "experiment_name": "test",
        "step_counter": 2,
        "autolog": False,
        "run_dir_root": "/tmp/run",
        "created_at_ms": 1234,
    })
    assert obs._created_at_ms == 1234


def test_link_traces_scoped_to_run_dir():
    obs = _make_observer(tracking_uri="http://mlflow", run_dir_root="/tmp/run")
    obs._created_at_ms = 100
    trace_match = MagicMock()
    trace_match.info.tags = {"run_dir": "/tmp/run"}
    trace_match.info.timestamp_ms = 150
    trace_match.info.request_id = "req-1"
    trace_other = MagicMock()
    trace_other.info.tags = {"run_dir": "/tmp/other"}
    trace_other.info.timestamp_ms = 150
    trace_other.info.request_id = "req-2"

    client = MagicMock()
    client.get_experiment_by_name.return_value = MagicMock(experiment_id="exp-1")
    client.search_traces.return_value = [trace_match, trace_other]

    import sys
    from unittest.mock import patch

    mlflow_module = MagicMock()
    mlflow_module.MlflowClient.return_value = client
    with patch.dict(sys.modules, {"mlflow": mlflow_module}):
        with patch("time.sleep"):
            obs._link_traces_to_run()

    client.set_trace_tag.assert_called_once_with(
        "req-1",
        "mlflow.source.run_id",
        "test_run",
    )
