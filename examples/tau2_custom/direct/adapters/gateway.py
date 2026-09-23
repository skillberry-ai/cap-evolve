"""LLM access for the tau2 runner on the DIRECT arm: one OpenAI-compatible gateway.

Both call classes go STRAIGHT to the gateway here — there is no proxy in this arm:

* the **agent under test** reads the candidate tool surface, which the adapter installs
  into tau2's own airline environment in this process;
* the **user simulator** (and any judge) uses the same gateway, a different call class
  that must never see the capability.

Credentials come from the run owner's repo-root ``.env`` (``OPENAI_BASE_URL`` /
``OPENAI_API_BASE`` + ``OPENAI_API_KEY``), loaded by a tiny walker that ``setdefault``s —
no python-dotenv dependency, matching the existing examples. Nothing is hardcoded and
nothing is invented: a missing credential raises at CONFIG time rather than turning into
a wall of 401s, which would read as a bad capability rather than a bad config.

**No API key is ever placed in ``llm_args``.** tau2 records ``llm_args`` verbatim into its
results file (``info.agent_info.llm_args`` / ``info.user_info.llm_args``) — which is exactly
what ``trajectories()`` exposes, what cap-evolve copies into the optimizer's workdir, and
what ``store: git`` COMMITS every iteration. litellm reads ``OPENAI_API_KEY`` from the
environment for the ``openai/`` route, so omitting it costs nothing.

Resolution is LAZY: importing this module makes no network call, so ``cap-evolve check``
stays offline.
"""

from __future__ import annotations

import os
from pathlib import Path

# The gateway catalog id for the agent under test AND the user simulator. Gateway ids are
# ALIASES and CASE-SENSITIVE (``Azure/...`` and ``azure/...`` can coexist); this exact
# string was confirmed against the gateway's own /v1/models catalog at onboarding.
DEFAULT_GATEWAY_MODEL = "aws/gpt-oss-120b"

# tau2's sentinel for "route this call to the Skillberry proxy". That is the OTHER arm's
# delivery path; on this arm there is no proxy to route to, so it is refused by name
# rather than silently dialled.
SPA_AGENT_MODEL = "ibm/skillberry-local"

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
    ``openai/openai/...`` is a 404.
    """
    m = (model or "").strip()
    if not m or m.startswith("openai/"):
        return m
    return f"openai/{m}" if m.startswith(_GATEWAY_PREFIXES) else m


def _refuse_spa(m: str, who: str) -> None:
    if m == SPA_AGENT_MODEL:
        raise RuntimeError(
            f"{who} is set to {SPA_AGENT_MODEL!r}, tau2's sentinel for the Skillberry-proxy "
            "route. This project is the DIRECT arm: the candidate tool surface is installed "
            "in this process and there is no proxy running, so that model id would resolve "
            "to nothing. Use a gateway catalog id (e.g. aws/gpt-oss-120b), or onboard the "
            "spa arm as its own project.")


def agent_model() -> str:
    """The AGENT under test — a real gateway model on this arm."""
    load_env()
    m = os.environ.get("TAU2_AGENT_MODEL") or DEFAULT_GATEWAY_MODEL
    _refuse_spa(m, "TAU2_AGENT_MODEL")
    return normalize(m)


def user_model() -> str:
    """The USER SIMULATOR — also a real gateway model."""
    load_env()
    m = os.environ.get("TAU2_USER_MODEL") or DEFAULT_GATEWAY_MODEL
    _refuse_spa(m, "TAU2_USER_MODEL")
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
    assert normalize("aws/gpt-oss-120b") == "openai/aws/gpt-oss-120b"
    assert normalize(normalize("aws/gpt-oss-120b")) == "openai/aws/gpt-oss-120b", \
        "double-normalized — openai/openai/... 404s"
    for var, fn in (("TAU2_AGENT_MODEL", agent_model), ("TAU2_USER_MODEL", user_model)):
        os.environ[var] = SPA_AGENT_MODEL
        try:
            fn()
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{var}={SPA_AGENT_MODEL} must be refused on the direct arm")
        os.environ.pop(var)
    assert agent_model() == user_model() == "openai/aws/gpt-oss-120b"
    assert "api_key" not in llm_args(), "an api_key in llm_args gets committed by store: git"
    print("gateway.py self-check OK")
