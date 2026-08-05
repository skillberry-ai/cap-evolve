# capevolve-telemetry

Optional MLflow and OpenTelemetry observer backends for cap-evolve.
When enabled, every `RunDir.log_event()` call is forwarded to external
telemetry systems — MLflow for experiment metrics and OTel for distributed
traces. When not configured, cap-evolve runs exactly as before with zero
overhead.

## Install

```bash
# MLflow only
pip install capevolve-telemetry[mlflow]

# OpenTelemetry only
pip install capevolve-telemetry[otel]

# Both
pip install capevolve-telemetry[all]
```

## Quick start

Add an `observers:` section to your `capevolve.yaml`:

```yaml
observers:
  - backend: mlflow
    tracking_uri: http://localhost:5000
    experiment_name: my-experiment
    autolog: true            # capture every LLM call (litellm/openai)
  - backend: otel
    mlflow_tracking_uri: http://localhost:5000
    experiment_name: my-experiment
    service_name: cap-evolve
```

Start an MLflow server and run cap-evolve as usual:

```bash
mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri sqlite:///mlflow.db &

cap-evolve run --spec capevolve.yaml --project .capevolve/project
```

Open http://localhost:5000 to see:
- **Runs tab** — val_reward curve, cost_usd, optimizer_seconds, test_delta
- **Traces tab** — per-LLM-call traces with model input/output/tokens/latency
- **Artifacts tab** — candidate diffs, JOURNAL.md, optimizer JSON reports

## Run naming

Each `cap-evolve run` creates a new MLflow run inside the experiment.
By default the run name is auto-generated from the spec:

```
run_named1 | hill-climb | claude-code | claude-sonnet-4-6 | skill-package
```

Override it with `run_name` in your `capevolve.yaml`:

```yaml
run_name: tau2-airline-14b-gepa-v3
```

Spec metadata (`algorithm_skill`, `optimizer_skill`, `target_model`,
`capabilities`, `gate_mode`, `max_iterations`, etc.) is also logged as
MLflow tags so you can filter and compare runs in the experiment view.

## Disabling

Telemetry is **off by default**. It only activates when the `observers:`
section is present and uncommented in your spec YAML. To disable, comment
it out or remove it:

```yaml
# observers:
#   - backend: mlflow
#     ...
```

No code changes, no env vars — just config.

## Configuration reference

### MLflow observer

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `backend` | yes | — | Must be `mlflow` |
| `tracking_uri` | yes | — | MLflow server URL (e.g. `http://localhost:5000`) |
| `experiment_name` | no | `cap-evolve` | MLflow experiment name |
| `autolog` | no | `false` | Auto-instrument litellm/openai calls for per-call traces |

**Metrics logged:**

| Event | Metrics | Step |
|-------|---------|------|
| `splits` | params: split_train, split_val, split_test, split_seed | — |
| `baseline` | val_reward, val_stderr | 0 |
| `step` | val_reward, delta, cost_usd, opt_cost_usd, tokens, optimizer_seconds, runner_seconds | 1..N |
| `evaluate` | {split}\_{tag}\_reward, \_stderr, \_cost_usd, \_seconds | — |
| `finalize` | test_reward, test_baseline_reward, test_delta | — |

**Artifacts logged per step:**

| Artifact | Description |
|----------|-------------|
| `{cand}.diff` | Unified diff of capability changes vs parent |
| `JOURNAL.md` | Optimizer reasoning log (accumulates each iteration) |
| `{cand}_optimizer.json` | Full optimizer session output (model usage, cost) |
| `{cand}_error.txt` | Full error output when optimizer fails |

### OTel observer

Exports cap-evolve events as OTel spans. Set `mlflow_tracking_uri` to
route spans to MLflow's Traces tab, or `endpoint` for a standalone
collector (Jaeger, Grafana Tempo).

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `backend` | yes | — | Must be `otel` |
| `endpoint` | no | — | OTLP HTTP endpoint |
| `mlflow_tracking_uri` | no | — | Auto-derives endpoint + experiment_id for MLflow |
| `experiment_name` | no | `cap-evolve` | Used with `mlflow_tracking_uri` |
| `service_name` | no | `cap-evolve` | OTel resource service name |
