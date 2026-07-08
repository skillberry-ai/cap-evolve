import json
from pathlib import Path

from cap_evolve.telemetry import Telemetry, resolve_telemetry_config


def test_resolve_telemetry_config_disabled_by_default(tmp_path):
    cfg = resolve_telemetry_config({}, project_dir=tmp_path / "proj")
    assert cfg == {"enabled": False, "exporters": []}


def test_resolve_telemetry_config_from_cli_and_spec(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    cfg = resolve_telemetry_config(
        {
            "optimizer_skill": "mock",
            "algorithm_skill": "hill-climb",
            "capabilities": ["tools", "system-prompt"],
            "telemetry_experiment": "team-exp",
            "telemetry_tags": {"team": "ml"},
        },
        cli_telemetry="mlflow,otel",
        project_dir=project,
        run_ts="run_123",
    )
    assert cfg["enabled"] is True
    assert cfg["exporters"] == ["mlflow", "otel"]
    assert cfg["experiment_name"] == "team-exp"
    assert cfg["service_name"] == "cap-evolve/proj"
    assert cfg["tags"]["team"] == "ml"
    assert cfg["tags"]["run_ts"] == "run_123"


def test_telemetry_save_open_and_span_jsonl(tmp_path):
    run_dir = tmp_path / "run_1"
    tel = Telemetry(run_dir, {"enabled": True, "exporters": ["otel"], "service_name": "svc"})
    tel.save()

    reopened = Telemetry.open(run_dir)
    assert reopened.enabled is True
    with reopened.span("baseline", attributes={"cap_evolve.task_count": 3}):
        pass

    spans = [json.loads(line) for line in (run_dir / "otel_spans.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(spans) == 1
    assert spans[0]["name"] == "baseline"
    assert spans[0]["attributes"]["cap_evolve.task_count"] == 3
    assert spans[0]["duration_ms"] >= 0.0


def test_telemetry_iteration_and_finalize_are_noop_when_disabled(tmp_path):
    run_dir = tmp_path / "run_2"
    run_dir.mkdir()
    tel = Telemetry.disabled(run_dir)
    tel.log_iteration(
        candidate_id="cand_0001",
        accepted=True,
        parent_id="seed",
        current_val=0.2,
        candidate_val={"reward": 0.4, "stderr": 0.1, "cost_usd": 0.01, "tokens": 10, "seconds": 1.0},
        decision={"mode": "paired", "reason": "gain"},
        optimizer_seconds=0.5,
        optimizer_usd=0.02,
        optimizer_tokens=20,
    )
    tel.log_finalize({"best_id": "cand_0001", "test": {"reward": 0.5}, "test_baseline": {"reward": 0.3},
                      "test_delta": 0.2})
    assert not (run_dir / "telemetry_events.jsonl").exists()
    assert not (run_dir / "otel_spans.jsonl").exists()


def test_telemetry_iteration_logs_local_event(tmp_path):
    run_dir = tmp_path / "run_3"
    tel = Telemetry(run_dir, {"enabled": True, "exporters": ["otel"], "service_name": "svc"})
    tel.log_iteration(
        candidate_id="cand_0002",
        accepted=False,
        parent_id="cand_0001",
        current_val=0.7,
        candidate_val={"reward": 0.6, "stderr": 0.05, "cost_usd": 0.03, "tokens": 50, "seconds": 2.0},
        decision={"mode": "paired", "reason": "not significant"},
        optimizer_seconds=1.2,
        optimizer_usd=0.04,
        optimizer_tokens=80,
        optimizer_error="timeout",
    )
    events = [json.loads(line) for line in (run_dir / "telemetry_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["kind"] == "iteration"
    assert events[-1]["candidate_id"] == "cand_0002"
    assert events[-1]["accepted"] is False
    assert events[-1]["metrics"]["delta_vs_parent"] == -0.09999999999999998