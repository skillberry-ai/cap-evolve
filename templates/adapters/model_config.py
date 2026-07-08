"""Reusable model-wiring helper for any litellm-supported provider.

Drop this file next to your adapter and import it::

    import model_config
    MODEL      = model_config.MODEL          # litellm model string
    llm_kwargs = model_config.llm_kwargs()    # api_base, api_key, temperature, …

All configuration is via environment variables (or a repo-root ``.env`` file).
Set **MODEL** (required) and, depending on the provider, the matching credential
vars. Examples:

    # OpenAI
    MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…

    # Azure OpenAI
    MODEL=azure/gpt-4o  AZURE_API_KEY=…  AZURE_API_BASE=https://….openai.azure.com

    # Anthropic
    MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=sk-ant-…

    # Google Vertex AI (uses ADC — no key needed if gcloud auth is set up)
    MODEL=vertex_ai/claude-sonnet-4-6

    # Ollama (local)
    MODEL=ollama/qwen2.5:7b-instruct  API_BASE=http://localhost:11434

    # IBM RITS (via hosted_vllm)
    MODEL=hosted_vllm/openai/gpt-oss-120b  RITS_API_KEY=…  API_BASE=https://…/v1

    # LiteLLM Proxy (any model behind a proxy)
    MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000
    LITELLM_PROXY_API_KEY=sk-…

    # Any OpenAI-compatible endpoint
    MODEL=openai/my-model  OPENAI_API_KEY=…  OPENAI_API_BASE=http://my-endpoint/v1

The helper is LAZY — it does NO network at import time so ``cap-evolve check``
stays offline. The first call to ``llm_kwargs()`` resolves credentials.
"""

from __future__ import annotations

import os
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
            except Exception:
                pass
            break


def _env(name: str, default: str = "") -> str:
    """Get an env var after loading .env."""
    _load_env()
    return os.environ.get(name, default)


# ---- public API ---------------------------------------------------------

MODEL: str = _env("MODEL", "gpt-4.1-mini")
"""The litellm model string — set via the ``MODEL`` env var."""


def llm_kwargs() -> dict[str, Any]:
    """Return provider-appropriate kwargs for ``litellm.completion(**llm_kwargs())``.

    Resolves ``api_base``, ``api_key``, ``extra_headers``, and ``temperature``
    from env vars. Provider detection is based on the MODEL prefix — the same
    logic litellm uses internally, so no extra mapping is needed.
    """
    _load_env()
    kwargs: dict[str, Any] = {}

    # Generic overrides (work for any provider).
    api_base = os.environ.get("API_BASE") or os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")

    # Provider-specific env vars (litellm convention).
    model_lower = MODEL.lower()
    if model_lower.startswith("azure/"):
        api_base = api_base or os.environ.get("AZURE_API_BASE")
        api_key = api_key or os.environ.get("AZURE_API_KEY")
    elif model_lower.startswith("anthropic/"):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    elif model_lower.startswith("hosted_vllm/"):
        rits_key = os.environ.get("RITS_API_KEY")
        if rits_key:
            api_key = api_key or rits_key
            kwargs["extra_headers"] = {"RITS_API_KEY": rits_key}
    elif model_lower.startswith("litellm_proxy/"):
        api_base = api_base or os.environ.get("LITELLM_PROXY_API_BASE")
        api_key = api_key or os.environ.get("LITELLM_PROXY_API_KEY")

    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    kwargs["temperature"] = float(os.environ.get("TEMPERATURE", "0.0"))
    return kwargs
