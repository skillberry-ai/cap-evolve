# Observability Integration

cap-evolve ships a generic **observer protocol** that lets you push run events
(iterations, gate decisions, metrics, errors) to any external observability
platform — MLflow, OpenTelemetry, or your own custom backend — without
modifying the core loop.

## Quick start

### 1. Install the extras you need

```bash
# MLflow only
pip install cap-evolve-core[mlflow]

# OpenTelemetry only
pip install cap-evolve-core[otel]

# Both
pip install cap-evolve-core[observability]
```

### 2. Add observers to your `capevolve.yaml`

```yaml
observers:
  - backend: mlflow
    experiment_name: cap-evolve/my-project
    tracking_uri: http://localhost:5000

  - backend: otel
    service_name: cap-evolve
```

### 3. Use observers programmatically

```python
from cap_evolve import RunDir, RunObserver
from cap_evolve.observers_mlflow import MLflowObserver
from cap_evolve.observers_otel import OTelObserver

# Create or open a run directory
rd = RunDir.create(base_path)

# Attach observers
rd.add_observer(MLflowObserver(experiment_name="my-exp"))
rd.add_observer(OTelObserver(service_name="cap-evolve"))

# Signal run start (optional but recommended)
rd.notify_run_start({"budget": {"max_iterations": 10}})

# ... run your optimization loop ...
# Every rd.log_event() call automatically fans out to all observers.

# Signal run end
rd.notify_run_end({"test_reward": 0.85})
```

## Architecture

```
RunDir.log_event("step", val=0.75, ...)
  │
  ├─ writes to events.jsonl  (always, local)
  │
  └─ for each attached observer:
       observer.on_event({"kind": "step", "val": 0.75, "t": ...})
```

Every observer receives the same dict that goes into the append-only
`events.jsonl`.  Observers are **fire-and-forget**: if an observer raises, the
exception is swallowed (logged at WARNING level) and the run continues.

## Writing a custom observer

Subclass `RunObserver` and override the hooks you need:

```python
from cap_evolve.observers import RunObserver

class MyObserver(RunObserver):
    def on_run_start(self, run_id: str, metadata: dict) -> None:
        print(f"Run {run_id} starting with {metadata}")

    def on_event(self, event: dict) -> None:
        kind = event.get("kind")
        if kind == "step":
            print(f"  Step: candidate={event.get('candidate')} val={event.get('val')}")

    def on_run_end(self, summary: dict) -> None:
        print(f"Run finished: {summary}")

    def flush(self) -> None:
        pass  # flush buffered data

    def close(self) -> None:
        pass  # release resources
```

### Registering a third-party backend

Third-party packages can register an observer backend via the
`capevolve.observers` entry-point group in their `pyproject.toml`:

```toml
[project.entry-points."capevolve.observers"]
mybackend = "my_package.observer:MyObserver"
```

Users can then reference it by name:

```yaml
observers:
  - backend: mybackend
    my_option: value
```

Or instantiate it programmatically:

```python
from cap_evolve.observers import observer_from_config

obs = observer_from_config({"backend": "mybackend", "my_option": "value"})
```

## Built-in backends

| Backend | Class | Install extra | Description |
|---------|-------|---------------|-------------|
| `null` | `NullObserver` | *(none)* | Default no-op; discards events |
| `mlflow` | `MLflowObserver` | `mlflow` | Logs metrics/params to MLflow Tracking |
| `otel` / `opentelemetry` | `OTelObserver` | `otel` | Emits spans + metrics to any OTel collector |

### MLflow observer options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `experiment_name` | str | `"cap-evolve"` | MLflow experiment name |
| `tracking_uri` | str | `None` | MLflow tracking URI (`MLFLOW_TRACKING_URI` env var fallback) |
| `run_name` | str | `None` | Human-readable MLflow run name |
| `tags` | dict | `{}` | Extra tags on the MLflow run |

### OpenTelemetry observer options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `service_name` | str | `"cap-evolve"` | OTel `service.name` resource attribute |
| `endpoint` | str | `None` | OTLP endpoint (`OTEL_EXPORTER_OTLP_ENDPOINT` env var fallback) |

## Event kinds

All event kinds emitted by cap-evolve are documented by the fields they carry.
Common kinds include:

- `splits` — dataset split created (train/val/test counts)
- `baseline` — baseline evaluation complete
- `evaluate` — a candidate scored on a split
- `step` — iteration result (accept/reject, val reward, delta)
- `gate_warning` — statistical gate anomaly
- `optimizer_error` — optimizer failed for a candidate
- `finalize` — sealed test evaluation
- `budget_warning` — budget threshold crossed
