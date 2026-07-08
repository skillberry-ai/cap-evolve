"""Optional observability integration for cap-evolve runs.

This module keeps the core runtime stdlib-only while allowing best-effort export to
external observability systems when the user opts in. Integrations are configured
from the run spec / CLI and are intentionally NON-BLOCKING: missing SDKs, exporter
errors, or malformed payloads never fail a run.

Current integrations:
- MLflow: logs run/iteration/finalize data via the ``mlflow`` CLI when available.
- OpenTelemetry: emits span-shaped JSON lines to a local file sink and, when the
  ``opentelemetry-sdk`` package is installed, also emits real spans through the
  global tracer provider.

The run dir stores the resolved config in ``telemetry.json`` so every phase can
re-open the same telemetry sink without threading a live object through subprocesses.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


def _json_default(obj):
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _safe_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", "/") else "-" for ch in str(value))
    return text.strip("-") or "cap-evolve"


def _bool_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_exporters(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip().lower() for p in value.split(",")]
        return [p for p in parts if p]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            s = str(item).strip().lower()
            if s:
                out.append(s)
        return out
    return []


def resolve_telemetry_config(spec: dict, *, cli_telemetry: str | None = None,
                             project_dir: Path | None = None, run_ts: str | None = None) -> dict:
    """Resolve telemetry config from spec + CLI override.

    Supported spec keys:
      telemetry: "mlflow,otel" | ["mlflow", "otel"]
      telemetry_experiment: explicit experiment/service name
      telemetry_tags: flat dict of extra tags
      mlflow_tracking_uri: MLflow tracking URI
      mlflow_experiment_name: explicit MLflow experiment name
      otel_service_name: explicit OTEL service name
      otel_export_file: explicit JSONL sink path
    """
    exporters = _normalize_exporters(cli_telemetry if cli_telemetry is not None else spec.get("telemetry"))
    exporters = [e for e in exporters if e in {"mlflow", "otel"}]
    if not exporters:
        return {"enabled": False, "exporters": []}

    project_dir = Path(project_dir).resolve() if project_dir is not None else None
    project_name = project_dir.name if project_dir is not None else "cap-evolve"
    experiment = (spec.get("telemetry_experiment")
                  or spec.get("mlflow_experiment_name")
                  or f"cap-evolve/{project_name}")
    service_name = spec.get("otel_service_name") or f"cap-evolve/{project_name}"
    tags = dict(spec.get("telemetry_tags") or {})
    if run_ts:
        tags.setdefault("run_ts", str(run_ts))
    return {
        "enabled": True,
        "exporters": exporters,
        "experiment_name": str(experiment),
        "service_name": str(service_name),
        "mlflow_tracking_uri": spec.get("mlflow_tracking_uri") or os.environ.get("MLFLOW_TRACKING_URI"),
        "mlflow_cli": spec.get("mlflow_cli") or shutil.which("mlflow") or "mlflow",
        "otel_export_file": str(spec.get("otel_export_file") or ""),
        "project_dir": str(project_dir) if project_dir is not None else None,
        "project_name": project_name,
        "run_name": str(run_ts or ""),
        "tags": tags,
    }


class Telemetry:
    """Best-effort telemetry sink reopened from ``telemetry.json`` per phase."""

    def __init__(self, run_dir: Path, config: dict):
        self.run_dir = Path(run_dir)
        self.config = dict(config or {})
        self.enabled = bool(self.config.get("enabled")) and bool(self.config.get("exporters"))
        self.exporters = list(self.config.get("exporters") or [])
        self.config_path = self.run_dir / "telemetry.json"
        self.events_path = self.run_dir / "telemetry_events.jsonl"
        self.spans_path = self.run_dir / "otel_spans.jsonl"
        self.mlflow_state_path = self.run_dir / "mlflow_state.json"
        self._otel_provider = None
        self._otel_tracer = None

    @classmethod
    def disabled(cls, run_dir: Path) -> "Telemetry":
        return cls(run_dir, {"enabled": False, "exporters": []})

    @classmethod
    def open(cls, run_dir: Path) -> "Telemetry":
        path = Path(run_dir) / "telemetry.json"
        if not path.exists():
            return cls.disabled(run_dir)
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cfg = {"enabled": False, "exporters": []}
        return cls(run_dir, cfg)

    def save(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.config, indent=2, default=_json_default), encoding="utf-8")

    def _append_event(self, kind: str, payload: dict) -> None:
        rec = {"t": time.time(), "kind": kind, **payload}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=_json_default) + "\n")

    def _append_span(self, payload: dict) -> None:
        with self.spans_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=_json_default) + "\n")
        export_file = str(self.config.get("otel_export_file") or "").strip()
        if export_file:
            p = Path(export_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, default=_json_default) + "\n")

    def _mlflow_state(self) -> dict:
        if self.mlflow_state_path.exists():
            try:
                return json.loads(self.mlflow_state_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _write_mlflow_state(self, state: dict) -> None:
        self.mlflow_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _mlflow_env(self) -> dict:
        env = dict(os.environ)
        uri = self.config.get("mlflow_tracking_uri")
        if uri:
            env["MLFLOW_TRACKING_URI"] = str(uri)
        return env

    def _run_mlflow(self, args: list[str]) -> subprocess.CompletedProcess | None:
        cli = str(self.config.get("mlflow_cli") or "mlflow")
        try:
            return subprocess.run([cli, *args], capture_output=True, text=True, env=self._mlflow_env(), timeout=30)
        except Exception as e:  # noqa: BLE001
            self._append_event("telemetry_warning", {"exporter": "mlflow", "error": str(e)[:500], "args": args})
            return None

    def _ensure_mlflow_run(self, *, nested: bool, run_name: str, tags: dict | None = None) -> str | None:
        state = self._mlflow_state()
        key = "root_run_id" if not nested else f"nested:{run_name}"
        if state.get(key):
            return state[key]
        args = ["runs", "create", "--experiment-name", str(self.config.get("experiment_name") or "cap-evolve"),
                "--run-name", run_name]
        if nested and state.get("root_run_id"):
            args += ["--parent-run-id", state["root_run_id"]]
        proc = self._run_mlflow(args)
        if proc is None or proc.returncode != 0:
            self._append_event("telemetry_warning", {
                "exporter": "mlflow", "error": (proc.stderr.strip() if proc else "mlflow unavailable"),
                "stdout": (proc.stdout.strip() if proc else ""), "args": args,
            })
            return None
        run_id = None
        try:
            obj = json.loads(proc.stdout)
            run_id = (((obj.get("run") or {}).get("info") or {}).get("run_id"))
        except Exception:  # noqa: BLE001
            run_id = None
        if not run_id:
            self._append_event("telemetry_warning", {
                "exporter": "mlflow", "error": "could not parse run_id", "stdout": proc.stdout[-500:],
            })
            return None
        state[key] = run_id
        self._write_mlflow_state(state)
        if tags:
            self._mlflow_set_tags(run_id, tags)
        return run_id

    def _mlflow_set_tags(self, run_id: str, tags: dict) -> None:
        for k, v in (tags or {}).items():
            proc = self._run_mlflow(["runs", "set-tag", "--run-id", run_id, "--key", str(k), "--value", str(v)])
            if proc is None or proc.returncode != 0:
                self._append_event("telemetry_warning", {
                    "exporter": "mlflow", "error": (proc.stderr.strip() if proc else "mlflow unavailable"),
                    "stdout": (proc.stdout.strip() if proc else ""), "run_id": run_id, "tag": str(k),
                })

    def _mlflow_log_metrics(self, run_id: str, metrics: dict) -> None:
        for k, v in (metrics or {}).items():
            if v is None:
                continue
            proc = self._run_mlflow(["runs", "log-metric", "--run-id", run_id, "--key", str(k), "--value", str(v)])
            if proc is None or proc.returncode != 0:
                self._append_event("telemetry_warning", {
                    "exporter": "mlflow", "error": (proc.stderr.strip() if proc else "mlflow unavailable"),
                    "stdout": (proc.stdout.strip() if proc else ""), "run_id": run_id, "metric": str(k),
                })

    def _mlflow_log_params(self, run_id: str, params: dict) -> None:
        for k, v in (params or {}).items():
            if v is None:
                continue
            proc = self._run_mlflow(["runs", "log-parameter", "--run-id", run_id, "--key", str(k), "--value", str(v)])
            if proc is None or proc.returncode != 0:
                self._append_event("telemetry_warning", {
                    "exporter": "mlflow", "error": (proc.stderr.strip() if proc else "mlflow unavailable"),
                    "stdout": (proc.stdout.strip() if proc else ""), "run_id": run_id, "param": str(k),
                })

    def _mlflow_log_artifact(self, run_id: str, path: Path) -> None:
        if not Path(path).exists():
            return
        proc = self._run_mlflow(["runs", "log-artifact", "--run-id", run_id, "--local-file", str(path)])
        if proc is None or proc.returncode != 0:
            self._append_event("telemetry_warning", {
                "exporter": "mlflow", "error": (proc.stderr.strip() if proc else "mlflow unavailable"),
                "stdout": (proc.stdout.strip() if proc else ""), "run_id": run_id, "artifact": str(path),
            })

    def _otel_tracer_obj(self):
        if self._otel_tracer is not None:
            return self._otel_tracer
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            class _JsonlExporter:
                def __init__(self, sink):
                    self._sink = sink

                def export(self, spans):
                    for span in spans:
                        attrs = dict(span.attributes or {})
                        self._sink({
                            "trace_id": format(span.context.trace_id, "032x"),
                            "span_id": format(span.context.span_id, "016x"),
                            "name": span.name,
                            "start_time_unix_nano": span.start_time,
                            "end_time_unix_nano": span.end_time,
                            "attributes": attrs,
                            "status": str(getattr(span.status, "status_code", "")),
                        })
                    return None

                def shutdown(self):
                    return None

            provider = TracerProvider(resource=Resource.create({
                "service.name": str(self.config.get("service_name") or "cap-evolve")
            }))
            provider.add_span_processor(SimpleSpanProcessor(_JsonlExporter(self._append_span)))
            trace.set_tracer_provider(provider)
            self._otel_provider = provider
            self._otel_tracer = trace.get_tracer("cap_evolve.telemetry")
        except Exception as e:  # noqa: BLE001
            self._append_event("telemetry_warning", {"exporter": "otel", "error": str(e)[:500]})
            self._otel_tracer = False
        return None if self._otel_tracer is False else self._otel_tracer

    def log_run_start(self, *, run_dir: Path, spec: dict) -> None:
        if not self.enabled:
            return
        payload = {
            "run_dir": str(run_dir),
            "experiment_name": self.config.get("experiment_name"),
            "service_name": self.config.get("service_name"),
            "exporters": self.exporters,
        }
        self._append_event("run_start", payload)
        if "mlflow" in self.exporters:
            tags = {"cap_evolve.run_dir": str(run_dir), **dict(self.config.get("tags") or {})}
            run_id = self._ensure_mlflow_run(nested=False, run_name=_safe_name(run_dir.name), tags=tags)
            if run_id:
                params = {
                    "algorithm": spec.get("algorithm_skill"),
                    "optimizer": spec.get("optimizer_skill"),
                    "optimizer_model": spec.get("optimizer_model"),
                    "runner_model": spec.get("runner_model") or spec.get("model"),
                    "num_trials": spec.get("num_trials"),
                    "gate_k_se": spec.get("gate_k_se"),
                    "capabilities": ",".join(spec.get("capabilities") or []),
                    "max_iterations": spec.get("max_iterations"),
                    "max_metric_calls": spec.get("max_metric_calls"),
                }
                self._mlflow_log_params(run_id, params)

    def log_iteration(self, *, candidate_id: str, accepted: bool, parent_id: str | None,
                      current_val: float | None, candidate_val: dict, decision: dict,
                      optimizer_seconds: float, optimizer_usd: float, optimizer_tokens: int,
                      optimizer_error: str | None = None) -> None:
        if not self.enabled:
            return
        reward = candidate_val.get("reward")
        stderr = candidate_val.get("stderr")
        metrics = {
            "val_reward": reward,
            "val_stderr": stderr,
            "runner_cost_usd": candidate_val.get("cost_usd"),
            "runner_tokens": candidate_val.get("tokens"),
            "runner_seconds": candidate_val.get("seconds"),
            "optimizer_cost_usd": optimizer_usd,
            "optimizer_tokens": optimizer_tokens,
            "optimizer_seconds": optimizer_seconds,
            "accepted": 1 if accepted else 0,
            "delta_vs_parent": (reward - current_val) if reward is not None and current_val is not None else None,
        }
        payload = {
            "candidate_id": candidate_id,
            "parent_id": parent_id,
            "accepted": accepted,
            "metrics": metrics,
            "decision": decision,
            "optimizer_error": optimizer_error,
        }
        self._append_event("iteration", payload)
        if "mlflow" in self.exporters:
            run_id = self._ensure_mlflow_run(nested=True, run_name=_safe_name(candidate_id), tags={
                "cap_evolve.parent_id": parent_id or "",
                "cap_evolve.accepted": str(bool(accepted)).lower(),
            })
            if run_id:
                self._mlflow_log_metrics(run_id, metrics)
                self._mlflow_log_params(run_id, {
                    "candidate_id": candidate_id,
                    "parent_id": parent_id,
                    "decision_mode": decision.get("mode"),
                    "decision_reason": decision.get("reason"),
                })
        if "otel" in self.exporters:
            attrs = {
                "cap_evolve.candidate_id": candidate_id,
                "cap_evolve.parent_id": parent_id or "",
                "cap_evolve.accepted": bool(accepted),
                "cap_evolve.val_reward": reward,
                "cap_evolve.val_stderr": stderr,
                "cap_evolve.optimizer_cost_usd": optimizer_usd,
                "cap_evolve.optimizer_tokens": optimizer_tokens,
                "cap_evolve.optimizer_seconds": optimizer_seconds,
                "cap_evolve.runner_cost_usd": candidate_val.get("cost_usd"),
                "cap_evolve.runner_tokens": candidate_val.get("tokens"),
                "cap_evolve.runner_seconds": candidate_val.get("seconds"),
            }
            with self.span("evaluate", attributes=attrs):
                pass
            with self.span("gate", attributes={
                "cap_evolve.candidate_id": candidate_id,
                "cap_evolve.accepted": bool(accepted),
                "cap_evolve.reason": decision.get("reason") or "",
            }):
                pass

    def log_finalize(self, payload: dict) -> None:
        if not self.enabled:
            return
        test = dict(payload.get("test") or {})
        base = dict(payload.get("test_baseline") or {})
        metrics = {
            "test_reward": test.get("reward"),
            "test_stderr": test.get("stderr"),
            "test_baseline_reward": base.get("reward"),
            "test_delta": payload.get("test_delta"),
        }
        self._append_event("finalize", {"metrics": metrics, "best_id": payload.get("best_id")})
        if "mlflow" in self.exporters:
            run_id = self._ensure_mlflow_run(nested=False, run_name=_safe_name(self.run_dir.name))
            if run_id:
                self._mlflow_log_metrics(run_id, metrics)
                for name in ("final.json", "report.md", "dashboard.html"):
                    self._mlflow_log_artifact(run_id, self.run_dir / name)
        if "otel" in self.exporters:
            with self.span("finalize", attributes={
                "cap_evolve.best_id": payload.get("best_id") or "",
                "cap_evolve.test_reward": test.get("reward"),
                "cap_evolve.test_baseline_reward": base.get("reward"),
                "cap_evolve.test_delta": payload.get("test_delta"),
            }):
                pass

    @contextmanager
    def span(self, name: str, *, attributes: dict | None = None):
        attrs = dict(attributes or {})
        start = time.time()
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        tracer = self._otel_tracer_obj() if self.enabled and "otel" in self.exporters else None
        otel_span = None
        if tracer is not None:
            try:
                otel_span = tracer.start_span(name)
                for k, v in attrs.items():
                    otel_span.set_attribute(k, v)
            except Exception as e:  # noqa: BLE001
                self._append_event("telemetry_warning", {"exporter": "otel", "error": str(e)[:500], "span": name})
                otel_span = None
        try:
            yield
        finally:
            end = time.time()
            payload = {
                "trace_id": trace_id,
                "span_id": span_id,
                "name": name,
                "start_time": start,
                "end_time": end,
                "duration_ms": round((end - start) * 1000.0, 3),
                "attributes": attrs,
            }
            if self.enabled and "otel" in self.exporters:
                self._append_span(payload)
            if otel_span is not None:
                try:
                    otel_span.end()
                except Exception:  # noqa: BLE001
                    pass