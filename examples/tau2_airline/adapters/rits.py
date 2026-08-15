"""RITS (IBM Research Inference) wiring for tau2 via litellm config.

We do NOT monkeypatch litellm or fork tau2. tau2 calls
``litellm.completion(model=..., messages=..., tools=..., **llm_args)`` with
``litellm.drop_params=True``, so RITS is passed entirely through the run config:
the model string ``hosted_vllm/openai/gpt-oss-120b`` plus an ``llm_args`` dict
carrying ``api_base``, ``api_key`` and an ``extra_headers`` with ``RITS_API_KEY``.

Endpoint resolution is LAZY and cached — it never runs at import time and never
during ``cap-evolve check`` (which does no live LLM call). The first time
``llm_args()`` is invoked the inference-info endpoint is queried (with retry) to
map the model to its RITS endpoint, then cached for the process.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

# litellm model string for the agent + user simulator.
LITELLM_MODEL = "hosted_vllm/openai/gpt-oss-120b"
# RITS model_name key returned by the inference-info endpoint.
_RITS_MODEL_NAME = "openai/gpt-oss-120b"

# Base inference host (the api_base is built per-model from the endpoint slug).
_API_URL = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com"
# Where to look up {model_name -> endpoint}.
_INFO_URL = "https://rits.fmaas.res.ibm.com/ritsapi/inferenceinfo"

_api_base_cache: Optional[str] = None


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


def _get_api_key() -> str:
    _load_env()
    key = os.environ.get("RITS_API_KEY")
    if not key:
        raise RuntimeError(
            "RITS_API_KEY not set. Put it in the repo-root .env (RITS_API_KEY=...)."
        )
    return key


def _resolve_api_base(key: str, *, retries: int = 5, backoff: float = 1.5) -> str:
    """Query the RITS inference-info endpoint and build the per-model api_base.

    Cached for the process. Retries a few times with exponential backoff.
    """
    global _api_base_cache
    if _api_base_cache is not None:
        return _api_base_cache

    import requests  # local import: not needed for check

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.get(_INFO_URL, headers={"RITS_API_KEY": key}, timeout=30)
            resp.raise_for_status()
            info = resp.json()
            endpoint = None
            for item in info:
                if item.get("model_name") == _RITS_MODEL_NAME:
                    endpoint = item.get("endpoint")
                    break
            if not endpoint:
                raise RuntimeError(
                    f"model_name {_RITS_MODEL_NAME!r} not found in RITS inference info"
                )
            slug = endpoint.rstrip("/").split("/")[-1]
            _api_base_cache = f"{_API_URL.rstrip('/')}/{slug}/v1"
            return _api_base_cache
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
    raise RuntimeError(f"Failed to resolve RITS endpoint after {retries} tries: {last_err}")


_registered_cost = False


def _register_zero_cost() -> None:
    """Tell litellm this RITS model is free (internal inference), so its cost
    lookup returns 0 instead of logging a noisy 'model isn't mapped yet' ERROR
    on every call. Honest: RITS runner spend is not metered here. Lazy + once."""
    global _registered_cost
    if _registered_cost:
        return
    try:
        import litellm

        zero = {
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "litellm_provider": "hosted_vllm",
            "mode": "chat",
        }
        litellm.register_model({LITELLM_MODEL: dict(zero), _RITS_MODEL_NAME: dict(zero)})
        _registered_cost = True
    except Exception:  # noqa: BLE001 — cost mapping is cosmetic; never block a run
        pass


def llm_args() -> dict:
    """Return the litellm ``llm_args`` dict for RITS (resolves + caches lazily)."""
    key = _get_api_key()
    api_base = _resolve_api_base(key)
    _register_zero_cost()
    return {
        "api_base": api_base,
        "api_key": key,
        "extra_headers": {"RITS_API_KEY": key},
        "temperature": 0.0,
    }


# ---------------------------------------------------------------------------
# Provider-aware model selection (default = RITS gpt-oss; override for claude).
# ---------------------------------------------------------------------------
# The agent and user-simulator models are env-overridable so the same adapter can
# run on RITS gpt-oss (default) OR on a claude model via the IBM Anthropic-compatible
# gateway (e.g. the on-demand integration test: TAU2_AGENT_MODEL=anthropic/claude-haiku-4-5).


# Vendor prefixes served by the IBM litellm PROXY (an OpenAI-compatible /v1 endpoint
# at ANTHROPIC_BASE_URL, catalog readable at /v1/models). A proxy model is reached as
# ``openai/<catalog-id>`` with api_base=<base>/v1 — NOT via litellm's native provider
# for that vendor, which would try to talk to AWS/Azure/GCP directly and 401.
_PROXY_PREFIXES = ("aws/", "azure/", "Azure/", "gcp/", "GCP/", "rits/")


def _is_proxy(model: str) -> bool:
    """True for a litellm-proxy catalog id, e.g. ``aws/gpt-oss-120b``.

    Checked BEFORE _is_anthropic, because ``aws/claude-opus-5`` is a proxy id that
    happens to contain "claude": routing it to the native anthropic provider would
    send a catalog id the Anthropic Messages API has never heard of.
    """
    return (model or "").startswith(_PROXY_PREFIXES)


def _is_anthropic(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith("anthropic/") or "claude" in m


def _normalize(model: str) -> str:
    """Prefix a proxy catalog id with ``openai/`` so litellm uses the OpenAI route."""
    return f"openai/{model}" if _is_proxy(model) else model


def agent_model() -> str:
    """litellm model string for the agent under test (default: RITS gpt-oss)."""
    return _normalize(os.environ.get("TAU2_AGENT_MODEL") or LITELLM_MODEL)


def user_model() -> str:
    """litellm model string for the user simulator (default: RITS gpt-oss)."""
    return _normalize(os.environ.get("TAU2_USER_MODEL") or LITELLM_MODEL)


def _proxy_args() -> dict:
    """litellm args for the IBM litellm proxy's OpenAI-compatible /v1 endpoint."""
    _load_env()
    base = os.environ.get("ANTHROPIC_BASE_URL")
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    missing = [n for n, v in (("ANTHROPIC_BASE_URL", base), ("ANTHROPIC_AUTH_TOKEN", token)) if not v]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Put them in the repo-root .env to run the "
            "agent/user on a litellm-proxy model (e.g. TAU2_AGENT_MODEL=aws/gpt-oss-120b)."
        )
    return {
        "api_base": base.rstrip("/") + "/v1",
        "api_key": token,
        "temperature": 0.0,
    }


def _gateway_args() -> dict:
    """litellm args for a claude model on the IBM Anthropic-compatible gateway.

    Reads ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN from the repo-root .env (or env).
    The gateway authenticates via a bearer token (Claude-Code convention); we pass it
    both as litellm's ``api_key`` (litellm's anthropic provider requires one) and as an
    ``Authorization: Bearer`` header so the gateway accepts it. LAZY: never at import.
    """
    _load_env()
    base = os.environ.get("ANTHROPIC_BASE_URL")
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    missing = [n for n, v in (("ANTHROPIC_BASE_URL", base), ("ANTHROPIC_AUTH_TOKEN", token)) if not v]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Put them in the repo-root .env to run the "
            "agent/user on a claude model via the Anthropic-compatible gateway."
        )
    return {
        "api_base": base,
        "api_key": token,
        "extra_headers": {"Authorization": f"Bearer {token}"},
        "temperature": 0.0,
    }


def llm_args_for(model: str) -> dict:
    """Per-model litellm args: proxy ids -> litellm proxy; claude -> IBM gateway; else RITS.

    ``model`` may already be normalized (``openai/aws/...``), so strip that prefix
    before classifying — otherwise a normalized proxy id falls through to RITS and
    the run dies on a missing RITS_API_KEY.
    """
    bare = model[len("openai/"):] if (model or "").startswith("openai/") else model
    if _is_proxy(bare):
        return _proxy_args()
    if _is_anthropic(bare):
        return _gateway_args()
    return llm_args()


if __name__ == "__main__":  # ponytail: self-check, no framework — `python adapters/rits.py`
    # Routing is a credential path: a mis-classified model silently 401s against the
    # wrong provider, or dies demanding a RITS_API_KEY the run never needed. The
    # ORDER (proxy before anthropic) is the part that regresses, so pin it.
    import os as _os

    _cases = [
        # model string                        -> route      (why it matters)
        ("aws/gpt-oss-120b",                     "proxy"),   # the agent under test
        ("aws/claude-opus-5",                    "proxy"),   # contains "claude" but IS a proxy id
        ("openai/aws/gpt-oss-120b",              "proxy"),   # already normalized — must not fall through
        ("azure/gpt-5.4",                        "proxy"),
        ("rits/google/gemma-4-31B",              "proxy"),
        ("anthropic/claude-haiku-4-5",           "gateway"), # native Anthropic-compatible gateway
        ("claude-sonnet-4-6",                    "gateway"),
        ("hosted_vllm/openai/gpt-oss-120b",      "rits"),    # the RITS default
    ]

    def _route(m: str) -> str:
        bare = m[len("openai/"):] if m.startswith("openai/") else m
        return "proxy" if _is_proxy(bare) else ("gateway" if _is_anthropic(bare) else "rits")

    for _m, _want in _cases:
        _got = _route(_m)
        assert _got == _want, f"{_m!r} routed to {_got}, expected {_want}"
        print(f"  ok  {_m:34s} -> {_got}")

    # _normalize must be idempotent: agent_model() is called more than once per run.
    assert _normalize("aws/gpt-oss-120b") == "openai/aws/gpt-oss-120b"
    assert _normalize(_normalize("aws/gpt-oss-120b")) == "openai/aws/gpt-oss-120b", \
        "double-normalized — openai/openai/... would 404"
    assert _normalize(LITELLM_MODEL) == LITELLM_MODEL, "RITS default must pass through untouched"

    # Env overrides reach the normalizer.
    _os.environ["TAU2_AGENT_MODEL"] = "aws/gpt-oss-120b"
    assert agent_model() == "openai/aws/gpt-oss-120b", agent_model()
    _os.environ.pop("TAU2_AGENT_MODEL")
    assert agent_model() == LITELLM_MODEL, "default must be the RITS model"

    print("rits.py self-check OK")
