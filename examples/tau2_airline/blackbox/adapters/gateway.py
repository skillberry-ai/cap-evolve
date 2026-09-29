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

# The sentinel model id that means "deliver this call through the Skillberry proxy" — the
# blackbox arm's switch, kept here so both arms share ONE credential/normalization path. It is
# a MODEL NAME, never a gateway catalog id: it must never be offered as a real model, and
# `normalize` leaves it untouched because the route is decided by exact string match.
SPA_AGENT_MODEL = "ibm/skillberry-local"

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
    if not m or m == SPA_AGENT_MODEL or m.startswith("openai/"):
        return m
    return f"openai/{m}" if m.startswith(_GATEWAY_PREFIXES) else m


def _bare(model: str) -> str:
    """Strip the litellm route prefix. litellm's cost lookup uses the UNPREFIXED id."""
    m = (model or "").strip()
    return m[len("openai/"):] if m.startswith("openai/") else m


def agent_model() -> str:
    """The AGENT under test.

    Defaults to a gateway catalog model (the direct arm). The blackbox arm selects itself by
    setting ``TAU2_AGENT_MODEL`` to :data:`SPA_AGENT_MODEL` — one env var is the whole arm
    switch here, so nothing has to sniff the spec.
    """
    load_env()
    return normalize(os.environ.get("TAU2_AGENT_MODEL") or DEFAULT_GATEWAY_MODEL)


def is_spa_route(model: str) -> bool:
    """Whether ``model`` is the sentinel that means "deliver this call through the proxy"."""
    return (model or "").strip() == SPA_AGENT_MODEL


def user_model() -> str:
    """The USER SIMULATOR — ALWAYS a real gateway model, never the proxy route.

    The refusal is a correctness rule, not defensiveness: proxying the simulator injects the
    optimized capability into the very thing that measures the agent, and the run would still
    produce a plausible-looking number.
    """
    load_env()
    m = os.environ.get("TAU2_USER_MODEL") or DEFAULT_GATEWAY_MODEL
    if is_spa_route(m):
        raise RuntimeError(
            "the user simulator must not be routed through the proxy: that injects the "
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


def agent_llm_args() -> dict:
    """litellm args for the PROXY-ROUTED agent (the blackbox arm).

    Deliberately minimal. The route to the proxy (``base_url`` / ``api_key`` /
    ``custom_llm_provider``) and this rollout's Skillberry context header are added by the
    tailoring module's agent factory, which is the only place that knows the rollout's
    ``env_id``. Putting an ``api_base`` here instead would either be redundant or fight it.
    """
    return {"temperature": 0.0}


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

    DEFAULTS TO THE USER-SIMULATOR MODEL, NOT THE AGENT'S. Under this arm the agent model is
    the SPA sentinel, which ``normalize()`` deliberately leaves unprefixed so the proxy route
    stays an exact string match — so litellm would have no provider for it and this probe would
    RAISE instead of probing. It is also the wrong thing to ask: the sentinel is not a gateway
    model at all, and what needs proving here is the GATEWAY credential path. ``user_model()``
    is the arm's guaranteed-real gateway id (it refuses the sentinel itself), which makes it
    both the working choice and the meaningful one. SPA's own health is the intervention
    skill's check, not this one's.
    """
    # Guard BEFORE importing litellm, so an explicitly-passed sentinel is refused by NAME and
    # offline, rather than surfacing as litellm's opaque "LLM Provider NOT provided" error.
    m = normalize(model) if model else user_model()
    if is_spa_route(m):
        raise RuntimeError(
            f"probe() cannot use the proxy sentinel {m!r}: it is a ROUTE, not a gateway model, "
            f"so litellm has no provider for it. probe() exists to prove the GATEWAY credential "
            f"path — pass a real gateway id, or leave it unset to use the user-simulator model. "
            f"The proxy's own health is checked by the blackbox intervention skill.")

    import litellm

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
    # The proxy sentinel passes through untouched: the route is an exact string match, so
    # normalizing it to openai/ibm/skillberry-local would silently disable the blackbox arm.
    assert normalize(SPA_AGENT_MODEL) == SPA_AGENT_MODEL
    assert is_spa_route(SPA_AGENT_MODEL) and not is_spa_route(DEFAULT_GATEWAY_MODEL)
    # probe() must REFUSE the sentinel by name, offline, before it reaches litellm. It used to
    # default to TAU2_AGENT_MODEL, which under this arm IS the sentinel — so the credential probe
    # raised litellm's "LLM Provider NOT provided" instead of probing anything.
    try:
        probe(SPA_AGENT_MODEL)
    except RuntimeError as e:
        assert "ROUTE, not a gateway model" in str(e), f"wrong refusal: {e}"
    else:
        raise AssertionError("probe() accepted the proxy sentinel — it cannot resolve")
    # Neutralize the operator's .env for the DEFAULTING checks below. Without this the first
    # agent_model() call lazily loads the repo-root .env, which re-supplies the TAU2_* vars we
    # just popped (`setdefault`), and the assertion silently tests the operator's machine
    # instead of this file's fallback logic. That is why this self-check passed from /tmp and
    # failed in place.
    globals()["_ENV_LOADED"] = True
    for var in ("TAU2_AGENT_MODEL", "TAU2_USER_MODEL"):
        os.environ.pop(var, None)
    assert agent_model() == user_model() == "openai/aws/gpt-oss-120b"
    # blackbox: one env var selects the arm, and the simulator must REFUSE the proxy route.
    os.environ["TAU2_AGENT_MODEL"] = SPA_AGENT_MODEL
    assert agent_model() == SPA_AGENT_MODEL
    os.environ["TAU2_USER_MODEL"] = SPA_AGENT_MODEL
    try:
        user_model()
        raise AssertionError("the user simulator must refuse the proxy route")
    except RuntimeError:
        pass
    os.environ.pop("TAU2_USER_MODEL")
    os.environ.pop("TAU2_AGENT_MODEL")
    assert agent_llm_args() == {"temperature": 0.0}, \
        "the proxy route + context header are the tailoring module's job, not the gateway's"
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
