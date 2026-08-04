"""Two silent-failure fixes from the lost pilot run (30682720920).

`azure/gpt-5.5` rejects a `temperature` override with HTTP 400, so every one of the 60 tasks
errored on its first LLM call. Eval spend was $0.00, the run finished in 9 minutes, wrote
baseline.json and final.json, passed the completion gate, and reported **success** with a
clean-looking 0.000 — indistinguishable from a real capability measurement.

Layer 1: `model_config` must not send an override to a model that pins temperature.
Layer 2: `assert_run.py` must FAIL a run whose rollouts were infra errors, so this can never
         be published as a result again.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODEL_CONFIG = REPO / "templates" / "adapters" / "model_config.py"
ASSERT_RUN = REPO / "ci" / "benchmarks" / "lib" / "assert_run.py"


def _model_config(monkeypatch, model, temperature=None):
    """Import model_config fresh with MODEL/TEMPERATURE set (MODEL is read at import)."""
    monkeypatch.setenv("MODEL", model)
    if temperature is None:
        monkeypatch.delenv("TEMPERATURE", raising=False)
    else:
        monkeypatch.setenv("TEMPERATURE", temperature)
    spec = importlib.util.spec_from_file_location("_mc_test", MODEL_CONFIG)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- layer 1: temperature ---------------------------------------------------

@pytest.mark.parametrize("model", [
    "azure/gpt-5.5",
    "litellm_proxy/azure/gpt-5.5",       # the form CI actually uses
    "azure/gpt-5.6-luna",
    "azure/gpt-5.3-codex",
    "Azure/gpt-5-2025-08-07",
])
def test_no_temperature_override_for_models_that_pin_it(monkeypatch, model):
    """Effective temperature becomes the model default — 1 for gpt-5.x — which is the only
    value these accept. Sending anything (even 1) risks the 400 that killed the pilot."""
    mc = _model_config(monkeypatch, model, "0.0")
    assert "temperature" not in mc.llm_kwargs(), f"{model} must get no temperature override"


@pytest.mark.parametrize("model", [
    "aws/gpt-oss-120b",
    "litellm_proxy/aws/claude-sonnet-4-5",
    "azure/gpt-4o",                      # gpt-4 family is unaffected
    "gcp/gemini-2.5-pro",
])
def test_temperature_still_sent_for_every_other_model(monkeypatch, model):
    """model_config is shared by five adapters — this change must be a no-op elsewhere."""
    mc = _model_config(monkeypatch, model, "0.0")
    assert mc.llm_kwargs()["temperature"] == 0.0


def test_blank_temperature_means_use_the_model_default(monkeypatch):
    mc = _model_config(monkeypatch, "aws/gpt-oss-120b", "")
    assert "temperature" not in mc.llm_kwargs()


@pytest.mark.parametrize("word", ["default", "model", "none", "DEFAULT"])
def test_sentinel_words_mean_use_the_model_default(monkeypatch, word):
    mc = _model_config(monkeypatch, "aws/gpt-oss-120b", word)
    assert "temperature" not in mc.llm_kwargs()


def test_explicit_nonzero_temperature_is_honoured(monkeypatch):
    mc = _model_config(monkeypatch, "aws/gpt-oss-120b", "0.7")
    assert mc.llm_kwargs()["temperature"] == 0.7


def test_default_when_unset_is_still_zero(monkeypatch):
    """Unset TEMPERATURE must keep meaning 0.0, not "model default"."""
    mc = _model_config(monkeypatch, "aws/gpt-oss-120b", None)
    assert mc.llm_kwargs()["temperature"] == 0.0


# ---- layer 2: the infra gate ------------------------------------------------

def _run_dir(tmp_path, per_task, *, iterations=2):
    rd = tmp_path / "run"
    rd.mkdir()
    (rd / "baseline.json").write_text(json.dumps(
        {"val": {"reward": 0.0 if all(p["reward"] == 0 for p in per_task) else 0.5,
                 "per_task": per_task}}))
    (rd / "final.json").write_text(json.dumps({"test": {"reward": 0.0}}))
    (rd / "state.json").write_text(json.dumps({"spent": {"iterations": iterations}}))
    return rd


def _assert_run(rd, *extra):
    return subprocess.run([sys.executable, str(ASSERT_RUN), str(rd),
                           "--min-iterations", "1", "--allow-regression", *extra],
                          capture_output=True, text=True)


def _errored(tid):
    return {"task_id": tid, "reward": 0.0, "n": 1,
            "raw": {"errored": True, "errored_trials": 1, "n_trials": 1}}


def _scored(tid, reward):
    return {"task_id": tid, "reward": reward, "n": 1,
            "raw": {"errored": False, "errored_trials": 0, "n_trials": 1}}


def test_all_infra_error_run_now_fails(tmp_path):
    """The pilot's exact shape: every task errored, 0.000, previously reported success."""
    rd = _run_dir(tmp_path, [_errored(f"t{i}") for i in range(60)])
    out = _assert_run(rd)
    assert out.returncode == 1, out.stdout
    assert "measured nothing" in out.stdout
    assert "60/60" in out.stdout


def test_a_genuine_all_zero_run_still_passes(tmp_path):
    """A model that simply fails every task — no infra error — is a real 0.000 result."""
    rd = _run_dir(tmp_path, [_scored(f"t{i}", 0.0) for i in range(10)])
    out = _assert_run(rd)
    assert out.returncode == 0, out.stdout


def test_a_minority_of_infra_errors_still_passes(tmp_path):
    """Flaky infra must not fail the suite — metrics.py already excludes those tasks."""
    per_task = [_errored("a"), _errored("b")] + [_scored(f"t{i}", 0.6) for i in range(8)]
    out = _assert_run(_run_dir(tmp_path, per_task))
    assert out.returncode == 0, out.stdout


def test_threshold_is_configurable(tmp_path):
    per_task = [_errored("a"), _errored("b")] + [_scored(f"t{i}", 0.6) for i in range(8)]
    out = _assert_run(_run_dir(tmp_path, per_task), "--max-infra-frac", "0.1")
    assert out.returncode == 1, out.stdout


def test_healthy_run_message_unchanged(tmp_path):
    rd = _run_dir(tmp_path, [_scored(f"t{i}", 0.6) for i in range(10)])
    out = _assert_run(rd)
    assert out.returncode == 0 and out.stdout.startswith("OK:")


def test_gate_matches_metrics_infra_classifier():
    """Both must use the same rule, or the report and the exit code can disagree."""
    import ast
    a = ast.parse(ASSERT_RUN.read_text(encoding="utf-8"))
    m = ast.parse((REPO / "ci" / "benchmarks" / "lib" / "metrics.py").read_text(encoding="utf-8"))
    def logic(tree):
        """The function body with its docstring stripped — the docstrings differ by design."""
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == "_infra_task":
                body = list(n.body)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                return ast.dump(ast.Module(body=body, type_ignores=[]))
        raise AssertionError("_infra_task not found")
    assert logic(a) == logic(m), (
        "assert_run and metrics disagree on what an infra error is — the report would render "
        "tasks as infra-error while the exit code judged them differently (or vice versa)"
    )
