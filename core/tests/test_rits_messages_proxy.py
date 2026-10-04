"""An ibm-rits optimizer gets a private /v1/messages proxy instead of lite-rits.

The claude-code optimizer needs the Anthropic Messages API. lite-rits answers /v1/messages with
HTTP 500 ("'metadata'"), so run_suite.sh starts a per-job LiteLLM proxy that calls the RITS
endpoint directly. These tests pin the parts that broke while it was being built by hand on
skillberry-1: the provider must be `hosted_vllm/` (with `openai/` some calls were sent in the
Responses API shape, and vLLM answered 400), and the key must stay in a private file.
"""

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
PROXY = LIB / "rits_messages_proxy.sh"
RUN_SUITE = LIB / "run_suite.sh"


def _bash(script: str, **env) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", f'set -uo pipefail\n. "{PROXY}"\n{script}'],
                          capture_output=True, text=True, env={**os.environ, **env})


def test_catalog_key_strips_only_the_rits_prefix():
    proc = _bash('rits_catalog_key "rits/google/gemma-4-31B-it"')
    assert proc.stdout == "google/gemma-4-31B-it"


def test_config_uses_hosted_vllm_and_the_rits_header(tmp_path):
    cfg = tmp_path / "config.yaml"
    proc = _bash(f'rits_proxy_config "{cfg}" "rits/google/gemma-4-31B-it" '
                 f'"https://rits.example/gemma-4-31b-it/" "sekret-key-123"')
    assert proc.returncode == 0, proc.stderr
    text = cfg.read_text()
    assert 'model_name: "rits/google/gemma-4-31B-it"' in text
    assert 'model: "hosted_vllm/google/gemma-4-31B-it"' in text
    assert "openai/" not in text
    assert 'api_base: "https://rits.example/gemma-4-31b-it/v1"' in text
    assert 'RITS_API_KEY: "sekret-key-123"' in text
    assert "drop_params: true" in text
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600


def test_missing_endpoint_fails_loudly(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\nexit 1\n")
    (fake_bin / "docker").chmod(0o755)
    proc = _bash('start_rits_messages_proxy "rits/google/gemma-4-31B-it" k; echo "rc=$?"',
                 PATH=f"{fake_bin}:/usr/bin:/bin", CAPEVOLVE_RITS_ENDPOINT="")
    assert "rc=1" in proc.stdout
    assert "no RITS endpoint" in proc.stderr


def test_run_suite_starts_the_proxy_only_for_an_ibm_rits_optimizer():
    src = RUN_SUITE.read_text(encoding="utf-8")
    hook = src[src.index('export ANTHROPIC_AUTH_TOKEN="$OPTIMIZER_API_KEY"'):]
    hook = hook[:hook.index("\nfi\n") + 4]
    # Right after the optimizer was resolved, so RESOLVED_PROVIDER is the optimizer's.
    assert 'if [ "$RESOLVED_PROVIDER" = "ibm-rits" ]; then' in hook
    assert 'start_rits_messages_proxy "$OPTIMIZER_MODEL_WIRE" "$OPTIMIZER_API_KEY" || exit 1' in hook
    before = src[:src.index(hook)]
    assert before.rindex('resolve_provider "$OPTIMIZER_MODEL"') > before.rindex('resolve_provider "$AGENT_MODEL"')


def test_every_claude_model_alias_points_at_the_proxied_model():
    src = PROXY.read_text(encoding="utf-8")
    for var in ("ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
                "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                "CLAUDE_CODE_SUBAGENT_MODEL"):
        assert f'{var}="$wire"' in src, var
