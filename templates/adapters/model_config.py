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

    kwargs["temperature"] = float(os.environ.get("TEMPERATURE", "0.0"))
    # Optional output cap. Set high for reasoning models (they spend tokens on a
    # hidden reasoning pass before the visible answer), or for long outputs (patches).
    max_tokens = os.environ.get("MAX_TOKENS")
    if max_tokens:
        kwargs["max_tokens"] = int(max_tokens)
    return kwargs
