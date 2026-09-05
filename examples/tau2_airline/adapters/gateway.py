"""LLM access for the tau2 airline runner: one OpenAI-compatible ETE gateway.

Both call classes go STRAIGHT to the gateway — there is no proxy in this project:

* the **agent under test** reads the candidate policy + tool surface, which the adapter
  installs into tau2's own airline environment in this process;
* the **user simulator** (and any judge) uses the same gateway. It is a different call
  class that must never see the capability, but it is the same endpoint.

The gateway takes a fixed base URL and a STANDARD BEARER KEY — no custom header, and
therefore no patching of the pinned tau2 clone.

Credentials come from the run owner's repo-root ``.env`` (``OPENAI_BASE_URL`` /
``OPENAI_API_BASE`` + ``OPENAI_API_KEY``), loaded by a tiny walker that ``setdefault``s —
no python-dotenv dependency, matching the other examples. Nothing is hardcoded and
nothing is invented: a missing credential raises at CONFIG time rather than turning into
a wall of 401s, which would read as a bad capability rather than a bad config.

**No API key is ever placed in ``llm_args``.** tau2 records ``llm_args`` verbatim into its
results file (``info.agent_info.llm_args`` / ``info.user_info.llm_args``) — which is exactly
what ``trajectories()`` exposes, what cap-evolve copies into the optimizer's working dir
each iteration, and what ``store: git`` COMMITS. litellm reads ``OPENAI_API_KEY`` from the
environment for the ``openai/`` route, so omitting it costs nothing.

Resolution is LAZY: importing this module makes no network call, so ``cap-evolve check``
stays offline.
"""

from __future__ import annotations

import os
from pathlib import Path

# The gateway catalog id for the agent under test AND the user simulator. Gateway ids are
# ALIASES and CASE-SENSITIVE (``Azure/...`` and ``azure/...`` can coexist in one catalog),
# so this exact string matters and case drift is a real failure mode.
DEFAULT_GATEWAY_MODEL = "aws/gpt-oss-120b"

# Vendor prefixes served by the gateway's OpenAI-compatible /v1 endpoint. Such an id is
# reached as ``openai/<catalog-id>`` — NOT via litellm's native provider for that vendor,
# which would try to talk to AWS/Azure/GCP directly and fail auth. Each prefix is one of
# the gateway's own catalog NAMESPACES (e.g. aws/gpt-oss-120b, rits/google/gemma-4-31B).
_GATEWAY_PREFIXES = ("aws/", "azure/", "Azure/", "gcp/", "GCP/", "rits/", "ibm/", "openai/")

_ENV_LOADED = False


def load_env() -> None:
    """Load the nearest ancestor ``.env`` into os.environ without overwriting. Idempotent."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env"
        if not env.exists():
            continue
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
        except OSError:
            pass
        break


def normalize(model: str) -> str:
    """Prefix a gateway catalog id with ``openai/`` so litellm takes the OpenAI route.

    IDEMPOTENT — ``agent_model()``/``user_model()`` are called more than once per run and
    ``openai/openai/...`` is a 404.
    """
    m = (model or "").strip()
    if not m or m.startswith("openai/"):
        return m
    return f"openai/{m}" if m.startswith(_GATEWAY_PREFIXES) else m


def _bare(model: str) -> str:
    """Strip the litellm route prefix. litellm's cost lookup uses the UNPREFIXED id."""
    m = (model or "").strip()
    return m[len("openai/"):] if m.startswith("openai/") else m


def agent_model() -> str:
    """The AGENT under test — a gateway catalog model."""
    load_env()
    return normalize(os.environ.get("TAU2_AGENT_MODEL") or DEFAULT_GATEWAY_MODEL)


def user_model() -> str:
    """The USER SIMULATOR — also a gateway catalog model."""
    load_env()
    return normalize(os.environ.get("TAU2_USER_MODEL") or DEFAULT_GATEWAY_MODEL)


def gateway_credentials() -> tuple[str, str]:
    """``(base_url, api_key)`` from the repo-root .env. Raises if either is missing."""
    load_env()
    base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    key = os.environ.get("OPENAI_API_KEY")
    missing = [n for n, v in (("OPENAI_BASE_URL (or OPENAI_API_BASE)", base),
                              ("OPENAI_API_KEY", key)) if not v]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Put them in the repo-root .env — the agent "
            "under test and the user simulator both need the gateway, and a wrong value "
            "401s every rollout, which reads as a bad capability rather than a bad config.")
    # Make both spellings available: litellm reads either.
    os.environ.setdefault("OPENAI_BASE_URL", base)
    os.environ.setdefault("OPENAI_API_BASE", base)
    os.environ.setdefault("OPENAI_API_KEY", key)
    return base, key


def llm_args() -> dict:
    """litellm args for a gateway call — used for BOTH the agent and the user simulator.

    NO api_key: see the module docstring (tau2 persists llm_args into the trajectories
    this run commits). The key is still validated here so a missing credential fails at
    config time.
    """
    base, _ = gateway_credentials()
    return {"api_base": base, "temperature": 0.0}


def llm_args_for(model: str) -> dict:
    """Per-model form of :func:`llm_args`.

    Every catalog id reaches the same OpenAI-compatible endpoint, so the model does not
    change the args. It exists so the adapter can stay explicit about which call class it
    is configuring, and so a split (a judge on a different endpoint) has a seam.

    It also registers ``model``'s zero cost, because this is the one function the runner
    calls per call class before the rollouts start. Without it litellm has no price entry
    and tau2 logs "This model isn't mapped yet" at ERROR level on EVERY completion, which
    buries real failures in the run log.
    """
    register_zero_cost(model, _bare(model))
    return llm_args()


def register_zero_cost(*models: str) -> None:
    """Tell litellm the gateway models are unmetered here, so its cost lookup returns 0
    instead of logging "model isn't mapped yet" on every call. Honest: gateway spend is
    not metered by this run, so a 0 in the cost panel means NOT MEASURED, not free.
    Never raises — cost mapping is cosmetic."""
    try:
        import litellm

        zero = {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0,
                "litellm_provider": "openai", "mode": "chat"}
        litellm.register_model({m: dict(zero) for m in models if m})
    except Exception:  # noqa: BLE001
        pass


def probe(model: str | None = None, *, max_tokens: int = 2048) -> dict:
    """One non-agent completion against the gateway. Returns a REDACTED verdict dict.

    A models LISTING would prove the key and not the alias, so this is a real completion
    with the RESOLVED id. ``max_tokens`` is generous on purpose: a reasoning model spends
    a tight budget on thinking and returns HTTP 200 with EMPTY content, which looks like
    a broken model rather than a truncated reply.
    """
    import litellm

    m = normalize(model or (os.environ.get("TAU2_AGENT_MODEL") or DEFAULT_GATEWAY_MODEL))
    base, _ = gateway_credentials()
    register_zero_cost(m)
    resp = litellm.completion(
        model=m, api_base=base, max_tokens=max_tokens, temperature=0.0,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    text = (resp.choices[0].message.content or "").strip()
    return {"model": m, "endpoint_host": base.split("//")[-1].split("/")[0],
            "content_len": len(text), "content_head": text[:40], "ok": bool(text)}


if __name__ == "__main__":  # self-check: routing is a credential path
    # normalize must be idempotent: agent_model() is called more than once per run.
    assert normalize("aws/gpt-oss-120b") == "openai/aws/gpt-oss-120b"
    assert normalize(normalize("aws/gpt-oss-120b")) == "openai/aws/gpt-oss-120b", \
        "double-normalized — openai/openai/... 404s"
    # A bare (non-catalog) id is left alone: litellm routes it by its own rules.
    assert normalize("claude-haiku-4-5") == "claude-haiku-4-5"
    # every catalog namespace normalizes the same way
    assert normalize("rits/google/gemma-4-31B") == "openai/rits/google/gemma-4-31B"
    assert normalize("") == ""
    for var in ("TAU2_AGENT_MODEL", "TAU2_USER_MODEL"):
        os.environ.pop(var, None)
    assert agent_model() == user_model() == "openai/aws/gpt-oss-120b"
    os.environ["OPENAI_BASE_URL"] = "https://example.invalid/v1"
    os.environ["OPENAI_API_KEY"] = "not-a-real-key"
    assert "api_key" not in llm_args(), "an api_key in llm_args gets committed by store: git"
    assert llm_args_for("aws/gpt-oss-120b") == llm_args()
    assert _bare("openai/aws/gpt-oss-120b") == "aws/gpt-oss-120b"
    assert _bare("aws/gpt-oss-120b") == "aws/gpt-oss-120b"
    # the price entry must exist under the id litellm actually looks up
    import litellm
    llm_args_for("openai/aws/gpt-oss-120b")
    assert "aws/gpt-oss-120b" in litellm.model_cost, \
        "unmapped model -> tau2 logs an ERROR on every completion"
    print("gateway.py self-check OK")
