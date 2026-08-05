"""MLflow observer backend.

Creates one MLflow run per cap-evolve optimisation run.  The ``run_id`` is
persisted in ``observer_state.json`` so subsequent phases (hill-climb,
finalize) resume the same MLflow run.

Metric mapping per event kind:

    splits       -> params (train/val/test sizes, seed)
    baseline     -> val_reward, val_stderr  (step 0)
    step         -> val_reward, delta, cost_usd, tokens, ... (step N)
    evaluate     -> <split>_<tag>_reward, ...
    finalize     -> test_reward, test_baseline_reward, test_delta
    budget_warning -> tags
    gepa_*/skillopt_* -> forward numeric fields as metrics
"""

from __future__ import annotations

from typing import Any


class MlflowObserver:
    """Logs cap-evolve events to an MLflow tracking server."""

    def __init__(
        self,
        *,
        run_id: str,
        tracking_uri: str,
        experiment_name: str,
        step_counter: int = 0,
        autolog: bool = False,
        run_dir_root: str = "",
    ):
        self._run_id = run_id
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name
        self._step = step_counter
        self._client = None
        self._finalized = False
        self._autolog = autolog
        self._run_dir_root = run_dir_root
        self._created_at_ms = int(__import__("time").time() * 1000)
        if autolog:
            self._enable_autolog()

    # ---- autolog -------------------------------------------------------------

    def _enable_autolog(self) -> None:
        """Enable MLflow auto-instrumentation for LLM calls (litellm/openai)."""
        import contextlib
        import io
        import os

        try:
            import mlflow

            with contextlib.redirect_stdout(io.StringIO()):
                if self._tracking_uri:
                    mlflow.set_tracking_uri(self._tracking_uri)
                mlflow.set_experiment(self._experiment_name)
                os.environ["MLFLOW_EXPERIMENT_NAME"] = self._experiment_name
                try:
                    mlflow.litellm.autolog()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    mlflow.openai.autolog()
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass

    # ---- construction ------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        run_dir_root: str = "",
        run_name: str = "",
        run_tags: dict[str, str] | None = None,
    ) -> "MlflowObserver":
        import mlflow

        tracking_uri = str(config.get("tracking_uri", ""))
        experiment_name = str(config.get("experiment_name", "cap-evolve"))
        autolog = bool(config.get("autolog", False))
        client = mlflow.MlflowClient(tracking_uri or None)
        exp = client.get_experiment_by_name(experiment_name)
        if exp is None:
            exp_id = client.create_experiment(experiment_name)
        else:
            exp_id = exp.experiment_id
        run = client.create_run(
            exp_id,
            run_name=run_name or run_dir_root or None,
        )
        run_id = run.info.run_id
        if run_dir_root:
            client.set_tag(run_id, "run_dir", run_dir_root)
        for k, v in (run_tags or {}).items():
            client.set_tag(run_id, k, str(v))
        return cls(
            run_id=run_id,
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            autolog=autolog,
            run_dir_root=run_dir_root,
        )

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "MlflowObserver":
        tracking_uri = state.get("tracking_uri", "")
        obs = cls(
            run_id=state["run_id"],
            tracking_uri=tracking_uri,
            experiment_name=state.get("experiment_name", "cap-evolve"),
            step_counter=int(state.get("step_counter", 0)),
            autolog=bool(state.get("autolog", False)),
            run_dir_root=state.get("run_dir_root", ""),
        )
        if "created_at_ms" in state:
            obs._created_at_ms = int(state["created_at_ms"])
        return obs

    # ---- helpers -----------------------------------------------------------

    def _ensure_client(self):
        if self._client is None:
            import mlflow

            self._client = mlflow.MlflowClient(
                self._tracking_uri or None
            )
        return self._client

    def _log_artifact_text(self, name: str, text: str) -> None:
        """Write ``text`` to a temp file and upload it as an MLflow artifact."""
        import os
        import shutil
        import tempfile

        client = self._ensure_client()
        artifact_dir = None
        try:
            artifact_dir = tempfile.mkdtemp()
            path = os.path.join(artifact_dir, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            client.log_artifact(self._run_id, path, artifact_path="optimizer")
        except Exception:  # noqa: BLE001
            pass
        finally:
            if artifact_dir and os.path.exists(artifact_dir):
                shutil.rmtree(artifact_dir, ignore_errors=True)

    def _log_candidate_artifacts(self, candidate_id: str, parent_id: str) -> None:
        """Upload candidate diff and journal as MLflow artifacts."""
        import subprocess
        from pathlib import Path

        if not self._run_dir_root:
            return
        run_dir = Path(self._run_dir_root)
        candidates = run_dir / "candidates"
        parent_dir = candidates / parent_id
        cand_dir = candidates / candidate_id

        if cand_dir.exists() and parent_dir.exists():
            try:
                result = subprocess.run(
                    ["diff", "-ruN", str(parent_dir), str(cand_dir)],
                    capture_output=True, text=True, timeout=10,
                )
                diff_text = result.stdout or "(no diff)"
                self._log_artifact_text(
                    f"{candidate_id}.diff", diff_text
                )
            except Exception:  # noqa: BLE001
                pass

        journal = run_dir / "JOURNAL.md"
        if journal.exists():
            try:
                self._log_artifact_text(
                    "JOURNAL.md", journal.read_text(encoding="utf-8")
                )
            except Exception:  # noqa: BLE001
                pass

    # ---- protocol ----------------------------------------------------------

    def on_event(self, kind: str, event: dict[str, Any]) -> None:
        client = self._ensure_client()
        ts = int(float(event.get("t", 0)) * 1000)

        if kind == "splits":
            for key in ("train", "val", "test", "seed"):
                v = event.get(key)
                if v is not None:
                    client.log_param(self._run_id, f"split_{key}", v)

        elif kind == "baseline":
            client.log_metric(self._run_id, "val_reward",
                              float(event.get("val", 0)), step=0, timestamp=ts)
            client.log_metric(self._run_id, "val_stderr",
                              float(event.get("stderr", 0)), step=0, timestamp=ts)

        elif kind == "step":
            self._step += 1
            s = self._step
            _METRIC_KEYS = {
                "val": "val_reward",
                "cost_usd": "cost_usd",
                "tokens": "tokens",
                "opt_cost_usd": "opt_cost_usd",
                "opt_tokens": "opt_tokens",
                "optimizer_seconds": "optimizer_seconds",
                "runner_seconds": "runner_seconds",
            }
            for raw_key, metric_name in _METRIC_KEYS.items():
                v = event.get(raw_key)
                if v is not None:
                    client.log_metric(self._run_id, metric_name,
                                      float(v), step=s, timestamp=ts)
            val = event.get("val")
            parent_val = event.get("parent_val")
            if val is not None and parent_val is not None:
                client.log_metric(self._run_id, "delta",
                                  float(val) - float(parent_val),
                                  step=s, timestamp=ts)
            cand = event.get("candidate", "")
            client.set_tag(self._run_id, f"step_{s}_candidate", str(cand))
            client.set_tag(self._run_id, f"step_{s}_accepted",
                           str(event.get("accept", "")))
            parent = event.get("parent", "seed")
            self._log_candidate_artifacts(str(cand), str(parent))
            opt_report = event.get("optimizer_report")
            if isinstance(opt_report, dict):
                import json
                self._log_artifact_text(
                    f"{cand}_optimizer.json",
                    json.dumps(opt_report, indent=2, default=str),
                )

        elif kind == "evaluate":
            split = event.get("split", "")
            tag = event.get("tag", "")
            prefix = f"{split}_{tag}_" if tag else f"{split}_"
            for key in ("reward", "stderr", "cost_usd", "tokens", "seconds"):
                v = event.get(key)
                if v is not None:
                    client.log_metric(self._run_id, f"{prefix}{key}",
                                      float(v), timestamp=ts)

        elif kind == "finalize":
            for key in ("test_reward", "test_baseline_reward", "test_delta"):
                v = event.get(key)
                if v is not None:
                    client.log_metric(self._run_id, key, float(v), timestamp=ts)
            best_id = event.get("best_id")
            if best_id is not None:
                client.set_tag(self._run_id, "best_id", str(best_id))
            self._finalized = True

        elif kind == "optimizer_error":
            cand = event.get("candidate", "unknown")
            error = event.get("error_full") or event.get("error", "")
            self._log_artifact_text(f"{cand}_error.txt", error)

        elif kind == "budget_warning":
            metric = event.get("metric", "unknown")
            pct = event.get("pct", "")
            client.set_tag(
                self._run_id,
                f"budget_warning_{metric}_{pct}pct",
                f"spent={event.get('spent')}/limit={event.get('limit')}",
            )

        elif kind == "intake":
            for key in ("usd", "seconds", "tokens"):
                v = event.get(key)
                if v is not None:
                    client.log_metric(self._run_id, f"intake_{key}",
                                      float(v), timestamp=ts)

        elif kind.startswith(("gepa_", "skillopt_")):
            for key, v in event.items():
                if key in ("t", "kind"):
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    client.log_metric(self._run_id, f"{kind}_{key}",
                                      float(v), timestamp=ts)

    def state(self) -> dict[str, Any]:
        return {
            "backend": "mlflow",
            "run_id": self._run_id,
            "tracking_uri": self._tracking_uri,
            "experiment_name": self._experiment_name,
            "step_counter": self._step,
            "autolog": self._autolog,
            "run_dir_root": self._run_dir_root,
            "created_at_ms": self._created_at_ms,
        }

    @property
    def run_id(self) -> str:
        return self._run_id

    def _link_traces_to_run(self) -> None:
        """Tag this run's unlinked traces in the experiment with this run's ID."""
        if not self._tracking_uri:
            return
        import time
        time.sleep(3)
        try:
            import mlflow

            client = mlflow.MlflowClient(self._tracking_uri or None)
            exp = client.get_experiment_by_name(self._experiment_name)
            if not exp:
                return
            traces = client.search_traces(
                locations=[exp.experiment_id],
            )
            for t in traces:
                tags = t.info.tags or {}
                if "mlflow.source.run_id" in tags:
                    continue
                if t.info.timestamp_ms and t.info.timestamp_ms < self._created_at_ms:
                    continue
                if tags.get("run_dir") != self._run_dir_root:
                    continue
                client.set_trace_tag(
                    t.info.request_id,
                    "mlflow.source.run_id",
                    self._run_id,
                )
        except Exception as e:  # noqa: BLE001
            if self._run_dir_root:
                try:
                    from pathlib import Path
                    Path(self._run_dir_root, "trace_link.log").write_text(f"{type(e).__name__}: {e}\n")
                except Exception:  # noqa: BLE001
                    pass

    def close(self) -> None:
        self._link_traces_to_run()
        if self._finalized:
            client = self._ensure_client()
            client.set_terminated(self._run_id)
