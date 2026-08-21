"""Reusable model-wiring helper for any litellm-supported provider.

Drop this file next to your adapter and import it::

    import model_config
    MODEL      = model_config.MODEL          # litellm model string
    llm_kwargs = model_config.llm_kwargs()    # api_base, api_key, temperature, …

All configuration is via environment variables (or a repo-root ``.env`` file).
Set **MODEL** (required) and, depending on the provider, the matching credential
vars. Switching providers is a one-line ``MODEL=`` change — no adapter edits.

    # OpenAI
    MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…

    # Anthropic
    MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=sk-ant-…

    # Google Vertex AI (uses ADC — no key needed if `gcloud auth` is set up)
    MODEL=vertex_ai/claude-sonnet-4-6

    # Azure OpenAI
    MODEL=azure/gpt-4o  AZURE_API_KEY=…  AZURE_API_BASE=https://….openai.azure.com

    # Ollama (local, free)
    MODEL=ollama/qwen2.5:7b-instruct  API_BASE=http://localhost:11434

    # LiteLLM Proxy — any model served behind a litellm proxy / gateway
    MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000
    LITELLM_PROXY_API_KEY=sk-…

    # Any other OpenAI-compatible endpoint
    MODEL=openai/my-model  OPENAI_API_KEY=…  OPENAI_API_BASE=http://my-endpoint/v1

For a provider not listed above, set the generic ``API_BASE`` / ``API_KEY`` vars
(or the provider's own litellm vars) — litellm routes on the ``MODEL`` prefix.

The helper is LAZY — it does NO network at import time so ``cap-evolve check``
stays offline. The first call to ``llm_kwargs()`` resolves credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _load_env() -> None:
    """Load the repo-root .env into os.environ (walk parents), without overwrite."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env"
        if env.exists():
            try:
                for raw in env.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, val)
            except Exception as exc:  # non-fatal: env vars may already be set
                print(f"model_config: could not read {env}: {exc}", file=sys.stderr)
            break


def _env(name: str, default: str = "") -> str:
    """Get an env var after loading .env."""
    _load_env()
    return os.environ.get(name, default)


# ---- public API ---------------------------------------------------------

MODEL: str = _env("MODEL", "gpt-4.1-mini")
"""The litellm model string — set via the ``MODEL`` env var."""


# Model families that PIN temperature to their own default and reject any override — even
# the value they claim to support. The gateway answers HTTP 400:
#
#   Unsupported value: 'temperature' does not support 0.0 with this model.
#   Only the default (1) value is supported.
#
# That fails EVERY rollout of a run, at $0.00 spend and in a few minutes, which reads exactly
# like a capability of 0.000 rather than a misconfiguration (run 30682720920 lost a whole
# pilot to it). Sending no override at all is safer than sending the value the error names,
# because a deployment may reject the parameter outright; the effective temperature is then
# the model's default, which for gpt-5.x IS 1.
#
# Matched against the last path segment of the resolved model id, so `azure/gpt-5.5`,
# `litellm_proxy/azure/gpt-5.6-luna` and `azure/gpt-5.3-codex` are all covered.
_TEMPERATURE_PINNED = ("gpt-5",)


def _temperature() -> float | None:
    """Resolve TEMPERATURE, or None meaning "send no override, use the model's default".

    A blank/`default`/`model` value is the explicit way to ask for the model's own default,
    which some models are the only way to call successfully.
    """
    raw = os.environ.get("TEMPERATURE", "0.0").strip()
    if raw == "" or raw.lower() in ("default", "model", "none"):
        return None
    return float(raw)


def _pins_temperature(model: str) -> bool:
    name = model.lower().rsplit("/", 1)[-1]
    return any(p in name for p in _TEMPERATURE_PINNED)


def llm_kwargs() -> dict[str, Any]:
    """Return provider-appropriate kwargs for ``litellm.completion(**llm_kwargs())``.

    Resolves ``api_base``, ``api_key`` and ``temperature`` from env vars. Provider
    detection is based on the MODEL prefix — the same routing litellm does
    internally, so no extra mapping is needed. Providers that authenticate out of
    band (e.g. Vertex AI via ADC) need no key here.
    """
    _load_env()
    kwargs: dict[str, Any] = {}

    # Generic overrides (work for any provider / OpenAI-compatible endpoint).
    api_base = os.environ.get("API_BASE") or os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")

    # Provider-specific env vars (litellm convention).
    model_lower = MODEL.lower()
    if model_lower.startswith("azure/"):
        api_base = api_base or os.environ.get("AZURE_API_BASE")
        api_key = api_key or os.environ.get("AZURE_API_KEY")
    elif model_lower.startswith("anthropic/"):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    elif model_lower.startswith("litellm_proxy/"):
        api_base = api_base or os.environ.get("LITELLM_PROXY_API_BASE")
        api_key = api_key or os.environ.get("LITELLM_PROXY_API_KEY")
    # vertex_ai/, ollama/, openai/, … need no special-casing: they use ADC,
    # API_BASE, or OPENAI_API_KEY handled by the generic block above.

    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    temperature = _temperature()
    if temperature is not None and not _pins_temperature(MODEL):
        kwargs["temperature"] = temperature
    # Optional output cap. Set high for reasoning models (they spend tokens on a
    # hidden reasoning pass before the visible answer), or for long outputs (patches).
    max_tokens = os.environ.get("MAX_TOKENS")
    if max_tokens:
        kwargs["max_tokens"] = int(max_tokens)
    effort = os.environ.get("REASONING_EFFORT", "").strip().lower()
    if effort and effort not in ("default", "model", "none"):
        _set_effort(kwargs, effort)
    return kwargs


def _set_effort(kwargs: dict[str, Any], effort: str) -> None:
    """Set reasoning_effort so it actually REACHES the provider.

    litellm validates parameters against its own per-model registry, and an OpenAI-compatible
    gateway serving a model it does not know (here ``openai/aws/gpt-oss-120b``) fails the
    check client-side with ``UnsupportedParamsError`` — the request never leaves the process.
    That is why a run can "set reasoning_effort" and change nothing: passing the kwarg alone
    raises, and dropping it via ``litellm.drop_params`` silently discards it.

    ``allowed_openai_params`` is the documented escape hatch and is MEASURED to work on this
    gateway: reasoning tokens 3 / 91 / 327 for low / provider-default / high on an identical
    prompt. The provider default is NOT "medium" — omitting the parameter gives 91 reasoning
    tokens, between low and high, so "default" is its own distinct setting and the comparison
    to make is always against omission, never against ``medium``.

    Note the gpt-oss "harmony" convention of declaring ``Reasoning: high`` in a system message
    does NOT work through this gateway (91 -> 107 reasoning tokens, i.e. noise); only the
    request parameter does.
    """
    kwargs["reasoning_effort"] = effort
    allowed = list(kwargs.get("allowed_openai_params") or [])
    if "reasoning_effort" not in allowed:
        allowed.append("reasoning_effort")
    kwargs["allowed_openai_params"] = allowed


def llm_kwargs_for(role: str) -> dict[str, Any]:
    """``llm_kwargs()`` with a per-ROLE reasoning_effort override.

    tau2-bench drives two LLMs per rollout: the AGENT under test, and the USER SIMULATOR
    that plays the customer. They are scored asymmetrically — only the agent's actions and
    messages are graded — but a run that hands both the same kwargs cannot tell you which
    one the setting helped. Worse, the simulator's own competence is part of the
    ENVIRONMENT: when it terminates a conversation early or invents a detail, the agent
    loses reward for a fault that is not the agent's.

    So the two are configurable independently:

        AGENT_REASONING_EFFORT=high  USER_REASONING_EFFORT=default

    Each falls back to ``REASONING_EFFORT``, then to the provider default (no override
    sent at all). Any change here is a disclosed configuration change and must be
    reported next to the number it produced — an agent read at high effort is NOT
    comparable to one read at the provider default.
    """
    kwargs = llm_kwargs()
    key = {"agent": "AGENT_REASONING_EFFORT", "user": "USER_REASONING_EFFORT"}[role]
    raw = os.environ.get(key, "").strip().lower()
    if raw:
        if raw in ("default", "model", "none"):
            kwargs.pop("reasoning_effort", None)
        else:
            _set_effort(kwargs, raw)
    return kwargs

