"""LLM access for the tau2 runner: the OpenAI-compatible gateway + the SPA route.

Two call classes, and keeping them apart is a CORRECTNESS rule, not a detail:

* the **agent under test** talks to the Skillberry Proxy-Agent (SPA), which injects the
  optimized capability. tau2's Skillberry build routes an agent whose model id is the
  sentinel ``ibm/skillberry-local`` to SPA itself (``SKILLBERRY_AGENT_URL``), so the
  agent's ``llm_args`` must carry NO ``api_base``/``api_key`` of ours;
* the **user simulator** (and any judge) goes STRAIGHT to the gateway. Proxying the
  simulator would inject the capability into the very thing measuring the agent.

Credentials come from the run owner's repo-root ``.env`` (``OPENAI_BASE_URL`` /
``OPENAI_API_BASE`` + ``OPENAI_API_KEY``), loaded by a tiny walker that ``setdefault``s —
no python-dotenv dependency, matching the existing examples. Nothing is hardcoded and
nothing is invented: a missing credential raises at config time rather than turning into
a wall of 401s that reads as a bad capability.

**No API key is ever placed in ``llm_args``.** tau2 records ``llm_args`` verbatim into its
results file (``info.agent_info.llm_args`` / ``info.user_info.llm_args``), which is exactly
what ``trajectories()`` exposes, what cap-evolve copies into the optimizer's workdir, and
what ``store: git`` commits. litellm reads ``OPENAI_API_KEY`` from the environment for the
``openai/`` route, so omitting it costs nothing.

Resolution is LAZY: importing this module makes no network call, so ``cap-evolve check``
stays offline.
"""

from __future__ import annotations

import os
from pathlib import Path

# tau2's own sentinel for "route this call to SPA" (tau2.config.SKILLBERRY_LLM_AGENT).
SPA_AGENT_MODEL = "ibm/skillberry-local"
# The gateway catalog id for the user simulator. Gateway ids are ALIASES and
# CASE-SENSITIVE; confirmed against the gateway's own /v1/models catalog at onboarding.
DEFAULT_GATEWAY_MODEL = "aws/gpt-oss-120b"

# Vendor prefixes served by the gateway's OpenAI-compatible /v1 endpoint. Such an id is
# reached as ``openai/<catalog-id>`` — NOT via litellm's native provider for that vendor,
# which would try to talk to AWS/Azure/GCP directly and fail auth.
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
    ``openai/openai/...`` is a 404. The SPA sentinel passes through untouched: tau2
    matches it by exact string to decide the SPA route.
    """
    m = (model or "").strip()
    if not m or m == SPA_AGENT_MODEL or m.startswith("openai/"):
        return m
    return f"openai/{m}" if m.startswith(_GATEWAY_PREFIXES) else m


def agent_model() -> str:
    """The AGENT under test. Default = the SPA sentinel (the whole point of this arm)."""
    load_env()
    return normalize(os.environ.get("TAU2_AGENT_MODEL") or SPA_AGENT_MODEL)


def user_model() -> str:
    """The USER SIMULATOR — always a real gateway model, never the SPA route."""
    load_env()
    m = os.environ.get("TAU2_USER_MODEL") or DEFAULT_GATEWAY_MODEL
    if m == SPA_AGENT_MODEL:
        raise RuntimeError(
            "the user simulator must not be routed through SPA: that injects the "
            "capability into the simulated user, which is what measures the agent")
    return normalize(m)


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
    # Make both spellings available: litellm reads either, and so do the two services.
    os.environ.setdefault("OPENAI_BASE_URL", base)
    os.environ.setdefault("OPENAI_API_BASE", base)
    os.environ.setdefault("OPENAI_API_KEY", key)
    return base, key


def upstream_llm_args() -> dict:
    """litellm args for the DIRECT-to-gateway path (the user simulator).

    NO api_key — see the module docstring. The key is still validated here so a missing
    credential fails at config time.
    """
    base, _ = gateway_credentials()
    return {"api_base": base, "temperature": 0.0}


def agent_llm_args() -> dict:
    """litellm args for the SPA-routed agent.

    Deliberately minimal: tau2's Skillberry path sets ``base_url``/``api_key`` for SPA
    itself and adds the Skillberry context headers, so anything we put here would either
    be redundant or fight it.
    """
    return {"temperature": 0.0}


def register_zero_cost(*models: str) -> None:
    """Tell litellm the gateway models are unmetered here, so its cost lookup returns 0
    instead of logging 'model isn't mapped yet' on every call. Honest: gateway spend is
    not metered by this run (and SPA reports no usage at all — a 0 in the cost panel
    means NOT MEASURED, not free). Never raises: cost mapping is cosmetic."""
    try:
        import litellm

        zero = {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0,
                "litellm_provider": "openai", "mode": "chat"}
        litellm.register_model({m: dict(zero) for m in models if m})
    except Exception:  # noqa: BLE001
        pass


def probe(model: str | None = None, *, max_tokens: int = 2048) -> dict:
    """One non-agent completion against the gateway. Returns a redacted verdict dict.

    A models LISTING would prove the key and not the alias, so this is a real completion
    with the RESOLVED id. ``max_tokens`` is generous on purpose: a reasoning model spends
    a tight budget on thinking and returns HTTP 200 with EMPTY content, which looks like
    a broken model rather than a truncated reply.
    """
    import litellm

    m = normalize(model or (os.environ.get("TAU2_USER_MODEL") or DEFAULT_GATEWAY_MODEL))
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
    assert normalize("aws/gpt-oss-120b") == "openai/aws/gpt-oss-120b"
    assert normalize(normalize("aws/gpt-oss-120b")) == "openai/aws/gpt-oss-120b", \
        "double-normalized — openai/openai/... 404s"
    assert normalize(SPA_AGENT_MODEL) == SPA_AGENT_MODEL, "the SPA sentinel must pass through"
    os.environ["TAU2_USER_MODEL"] = SPA_AGENT_MODEL
    try:
        user_model()
    except RuntimeError:
        pass
    else:
        raise AssertionError("routing the user simulator through SPA must be refused")
    os.environ.pop("TAU2_USER_MODEL")
    assert agent_model() == SPA_AGENT_MODEL
    print("gateway.py self-check OK")
