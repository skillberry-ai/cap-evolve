"""Provider-scoped credential resolution + ``auto`` provider probing.

Two footguns this module exists to remove:

1. **Cross-provider credential reuse.** A user has ``ANTHROPIC_API_KEY`` exported from
   another project, the spec selects ``openai``, and the run silently authenticates
   (or fails confusingly) with the wrong key. Resolution here is *provider-scoped*:
   each provider only ever looks at ITS OWN documented env vars (the ``env`` column of
   :data:`PROVIDERS`). A credential belonging to provider A is never applied to
   provider B — we raise :class:`CredentialError` naming the vars provider B accepts.
2. **Unknown provider.** ``provider: auto`` picks the first provider (in
   :data:`AUTO_ORDER`) whose own credential is present, and says which and why.

Precedence (documented once, here, and mirrored in ``docs/INSTALL.md``)::

    CLI flag  >  project capevolve.yaml  >  user config  >  built-in defaults

applied per FIELD (provider / base_url / credential env var), highest layer that
sets a non-empty value wins. The user config is ``~/.capevolve/config.yaml``
(override with ``$CAPEVOLVE_CONFIG``).

Secret handling — non-negotiable:

* Credential **values** live only in the process environment. No config layer may
  carry a secret: ``credential_env`` names an env var, it is not a place to paste a
  key. :class:`Resolved` therefore holds the env var NAME and never the value, so a
  resolved config cannot leak by being logged, repr'd, or JSON-dumped.
* Nothing in this module prints, logs, or embeds a credential value — not a prefix,
  not a length. Presence/absence only (``credential_present``).
* A probe sends a credential ONLY to the base URL of the same :data:`PROVIDERS` row
  the credential came from (see :func:`probe`), so a token can't reach a third party.
* **Endpoints are confidential too.** URL *userinfo* (``https://user:token@host/``) is a
  credential and is stripped the moment a base URL is resolved, so it can never be
  rendered or stored. And a base URL that is not one of the well-known public defaults
  is treated as sensitive: :meth:`Resolved.to_dict` and :func:`describe` report
  ``base_url: <custom>`` plus ``base_url_source`` (which precedence layer set it)
  instead of the value, because the hostname is exactly what identifies someone's
  internal infrastructure. The rule itself lives in ``dashboard.safe_url`` so every
  consumer — this module, the reducer, ``dashboard.html``, ``doctor`` — inherits it.

Stdlib only, zero runtime deps.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .dashboard import CUSTOM_URL, redact, safe_url, safe_urls_in_text, strip_url_userinfo
from .specfile import read_yaml

# ---------------------------------------------------------------------------
# The resolution table. One row per provider. `env` is ORDERED — the first var
# that is set wins, so the primary/documented name takes precedence over aliases.
#
# `header` is a (name, value-template) pair used ONLY when probing that same row's
# base_url; `{cred}` is substituted at call time from the env var this row named.
# Keeping url+header+env in ONE row is what makes a cross-provider send impossible.
# ---------------------------------------------------------------------------
PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "env": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
        "base_url_env": "ANTHROPIC_BASE_URL",
        "base_url": "https://api.anthropic.com",
        "probe_path": "/v1/models",
        "header": ("x-api-key", "{cred}"),
    },
    "openai": {
        "env": ["OPENAI_API_KEY"],
        "base_url_env": "OPENAI_BASE_URL",
        "base_url": "https://api.openai.com/v1",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "gemini": {
        "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "base_url_env": "GEMINI_BASE_URL",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "probe_path": "/models",
        "header": ("x-goog-api-key", "{cred}"),
    },
    "rits": {
        # RITS needs BOTH a key and a deployment URL; there is no usable default.
        "env": ["RITS_API_KEY"],
        "base_url_env": "RITS_API_URL",
        "base_url": "",
        "probe_path": "/models",
        "header": ("RITS_API_KEY", "{cred}"),
    },
    "watsonx": {
        "env": ["WATSONX_APIKEY", "WATSONX_API_KEY"],
        "base_url_env": "WATSONX_URL",
        "base_url": "",
        "probe_path": "/ml/v1/foundation_model_specs?version=2024-05-01",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "moonshot": {
        "env": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
        "base_url_env": "MOONSHOT_BASE_URL",
        "base_url": "https://api.moonshot.ai/v1",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "cursor": {
        "env": ["CURSOR_API_KEY"],
        "base_url_env": "CURSOR_BASE_URL",
        "base_url": "",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "factory": {
        "env": ["FACTORY_API_KEY"],
        "base_url_env": "FACTORY_BASE_URL",
        "base_url": "",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "github-copilot": {
        "env": ["COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"],
        "base_url_env": "COPILOT_BASE_URL",
        "base_url": "https://api.githubcopilot.com",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    "bob": {
        "env": ["BOBSHELL_API_KEY", "BOB_API_KEY"],
        "base_url_env": "BOBSHELL_URL",
        "base_url": "",
        "probe_path": "/models",
        "header": ("Authorization", "Bearer {cred}"),
    },
    # `mock` is the offline optimizer: no credential, no endpoint, never probed.
    "mock": {
        "env": [],
        "base_url_env": "",
        "base_url": "",
        "probe_path": "",
        "header": ("", ""),
    },
}

# Order `auto` considers providers in. First one whose OWN credential is present wins.
AUTO_ORDER = ["anthropic", "openai", "gemini", "rits", "watsonx", "moonshot",
              "github-copilot", "bob", "cursor", "factory"]

#: The documented precedence, highest first. Also the wording used in errors.
PRECEDENCE = ("CLI flag", "project capevolve.yaml", "user config", "built-in default")

# Optimizer/registry name -> provider, so `optimizer_skill: codex` implies `openai`.
OPTIMIZER_PROVIDER = {
    "claude-code": "anthropic", "codex": "openai", "gemini-cli": "gemini",
    "ibm-bob": "bob", "cursor": "cursor", "droid": "factory",
    "copilot": "github-copilot", "kimi": "moonshot", "mock": "mock",
}


class CredentialError(RuntimeError):
    """No usable, provider-scoped credential. Message names env VARS, never values."""


@dataclass(frozen=True)
class Resolved:
    """A resolved provider config. Deliberately holds NO credential value.

    ``credential_env`` is the *name* of the environment variable that carries the
    secret; read it at the point of use. That keeps every repr/log/JSON of this
    object secret-free by construction rather than by remembering to redact.

    ``base_url`` is the real endpoint (needed to make a request) but is
    ``repr=False``: a custom endpoint is confidential, so it must not appear in a
    traceback, a log line, or a JSON dump. Use :attr:`base_url_display` /
    :meth:`to_dict` for anything a human or a file will see. Userinfo has already
    been stripped by :func:`_resolve_base_url`, so even the in-memory value is
    credential-free.
    """

    provider: str
    credential_env: str = ""          # env var NAME, "" when nothing resolved
    base_url: str = field(default="", repr=False)   # real endpoint; never rendered
    sources: dict = field(default_factory=dict)   # field -> precedence layer
    reason: str = ""                  # human note (why `auto` picked this)

    @property
    def credential_present(self) -> bool:
        return bool(self.credential_env)

    @property
    def base_url_display(self) -> str:
        """Safe rendering: public defaults verbatim, anything else ``<custom>``."""
        return safe_url(self.base_url)

    @property
    def base_url_source(self) -> str:
        """Which precedence layer set the base URL — the actionable half of the value."""
        return self.sources.get("base_url", "built-in default" if self.base_url else "")

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "credential_env": self.credential_env,      # a NAME, not a value
            "credential_present": self.credential_present,
            "base_url": self.base_url_display,          # "<custom>" unless well-known
            "base_url_source": self.base_url_source,
            "sources": dict(self.sources),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Config layers
# ---------------------------------------------------------------------------

def user_config_path() -> Path:
    return Path(os.environ.get("CAPEVOLVE_CONFIG")
                or Path.home() / ".capevolve" / "config.yaml")


def read_user_config() -> dict:
    p = user_config_path()
    try:
        return read_yaml(p.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}


_SPEC_KEYS = {"provider": "provider", "base_url": "provider_base_url",
              "credential_env": "provider_credential_env"}


def _layered(cli: dict | None, project: dict | None, user: dict | None) -> tuple[dict, dict]:
    """Merge the layers per field. Returns ``(values, sources)``.

    Precedence: CLI > project > user > built-in (built-in applied by the caller).
    A layer that omits a field, or sets it empty, does not shadow a lower layer.
    """
    layers = [("CLI flag", cli or {}), ("project capevolve.yaml", project or {}),
              ("user config", user or {})]
    values, sources = {}, {}
    for field_name, spec_key in _SPEC_KEYS.items():
        for layer_name, data in layers:
            val = data.get(field_name) or data.get(spec_key)
            if val not in (None, ""):
                values[field_name] = str(val).strip()
                sources[field_name] = layer_name
                break
    return values, sources


def _scoped_credential_env(provider: str, prefer: str = "") -> str:
    """Name of the env var carrying ``provider``'s credential, or "" if none is set.

    Only :data:`PROVIDERS`\\ ``[provider]["env"]`` is consulted — this single-row
    lookup IS the provider-scoping guarantee. ``prefer`` (from config) must itself be
    one of that row's vars; a var belonging to another provider is refused upstream.
    """
    row = PROVIDERS[provider]
    names = [prefer] + list(row["env"]) if prefer else list(row["env"])
    for name in names:
        if os.environ.get(name):
            return name
    return ""


def _owner_of(env_name: str) -> str | None:
    for name, row in PROVIDERS.items():
        if env_name in row["env"]:
            return name
    return None


def _present_elsewhere(provider: str) -> list[str]:
    """Other providers whose credential IS present — for an actionable error only."""
    return [p for p in AUTO_ORDER if p != provider and _scoped_credential_env(p)]


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve(cli: dict | None = None, project: dict | None = None,
            user: dict | None = None, *, require_credential: bool = True,
            probe_fn=None) -> Resolved:
    """Resolve the provider + which env var holds its credential.

    ``cli`` / ``project`` / ``user`` are plain dicts (a parsed ``capevolve.yaml`` can
    be passed straight through as ``project``); ``user`` defaults to
    :func:`read_user_config`. Recognised keys per layer: ``provider``,
    ``provider_base_url``, ``provider_credential_env`` (short aliases
    ``base_url`` / ``credential_env`` also accepted).

    ``provider: auto`` selects the first provider in :data:`AUTO_ORDER` whose own
    credential is present; pass ``probe_fn`` (see :func:`probe`) to additionally
    require that the candidate's endpoint answers before selecting it.

    Raises :class:`CredentialError` when nothing resolves, or when the only
    credentials present belong to a *different* provider than the one selected.
    """
    if user is None:
        user = read_user_config()
    values, sources = _layered(cli, project, user)

    provider = values.get("provider", "")
    if not provider:
        # Built-in default: infer from the optimizer the spec names, else `auto`.
        opt = str((project or {}).get("optimizer_skill", "")).strip()
        provider = OPTIMIZER_PROVIDER.get(opt, "auto")
        sources["provider"] = ("built-in default (from optimizer_skill)" if opt in OPTIMIZER_PROVIDER
                               else "built-in default")

    if provider == "auto":
        return _resolve_auto(values, sources, probe_fn=probe_fn,
                             require_credential=require_credential)

    if provider not in PROVIDERS:
        raise CredentialError(
            f"unknown provider {provider!r} (from {sources.get('provider', 'config')}). "
            f"Known providers: {', '.join(sorted(PROVIDERS))}, or 'auto'.")

    prefer = values.get("credential_env", "")
    if prefer:
        owner = _owner_of(prefer)
        if owner not in (None, provider):
            # Refuse to cross the provider boundary even when explicitly asked to.
            raise CredentialError(
                f"provider_credential_env={prefer!r} belongs to provider {owner!r}, but the "
                f"selected provider is {provider!r}. Credentials are provider-scoped and are "
                f"never reused across providers. Set one of: "
                f"{', '.join(PROVIDERS[provider]['env']) or '(none — this provider takes no key)'}.")

    cred_env = _scoped_credential_env(provider, prefer)
    base_url = _resolve_base_url(provider, values, sources)

    if not cred_env and PROVIDERS[provider]["env"] and require_credential:
        raise CredentialError(_no_credential_message(provider, sources))

    return Resolved(provider=provider, credential_env=cred_env, base_url=base_url,
                    sources=sources,
                    reason=f"provider {provider!r} from {sources.get('provider', 'config')}")


def _resolve_base_url(provider: str, values: dict, sources: dict) -> str:
    """The endpoint to use, with URL userinfo stripped at the single point of resolution.

    Stripping here (rather than at each render site) means no downstream caller can
    ever hold a base URL carrying ``user:token@`` — the credential is gone before the
    value is stored on :class:`Resolved`, logged, or handed to :func:`probe`.
    """
    row = PROVIDERS[provider]
    if values.get("base_url"):
        return strip_url_userinfo(values["base_url"])
    env_name = row["base_url_env"]
    if env_name and os.environ.get(env_name):
        sources["base_url"] = f"environment ({env_name})"
        return strip_url_userinfo(os.environ[env_name])
    if row["base_url"]:
        sources["base_url"] = "built-in default"
    return row["base_url"]


def _no_credential_message(provider: str, sources: dict) -> str:
    accepted = ", ".join(PROVIDERS[provider]["env"])
    msg = [f"no credential found for provider {provider!r} "
           f"(selected via {sources.get('provider', 'config')}).",
           f"Set one of: {accepted}."]
    others = _present_elsewhere(provider)
    if others:
        msg.append(f"Credentials for {', '.join(others)} ARE present but belong to a different "
                   f"provider and are never reused — either export a {provider} credential, or "
                   f"select that provider explicitly (provider: {others[0]}) / use provider: auto.")
    msg.append("Precedence: " + " > ".join(PRECEDENCE) + ".")
    return " ".join(msg)


def _resolve_auto(values: dict, sources: dict, *, probe_fn=None,
                  require_credential: bool = True) -> Resolved:
    tried: list[str] = []
    for cand in AUTO_ORDER:
        cred_env = _scoped_credential_env(cand)
        if not cred_env:
            continue
        base_url = _resolve_base_url(cand, {}, sources)
        if not base_url and PROVIDERS[cand]["base_url_env"]:
            tried.append(f"{cand} (credential present, but {PROVIDERS[cand]['base_url_env']} unset)")
            continue
        if probe_fn is not None:
            ok, why = probe_fn(cand, base_url)
            if not ok:
                tried.append(f"{cand} (probe failed: {why})")
                continue
            note = f"probe of {cand} base URL succeeded"
        else:
            note = "credential present (no probe requested)"
        reason = (f"auto selected {cand!r}: {cred_env} is set and it is the highest-priority "
                  f"provider with its own credential; {note}."
                  + (f" Skipped: {'; '.join(tried)}." if tried else ""))
        s = dict(sources); s["provider"] = "auto probe"
        return Resolved(provider=cand, credential_env=cred_env, base_url=base_url,
                        sources=s, reason=reason)

    if not require_credential:
        return Resolved(provider="", sources=sources,
                        reason="auto found no provider with its own credential")
    detail = f" Considered but rejected: {'; '.join(tried)}." if tried else ""
    raise CredentialError(
        "provider: auto found no usable provider — none of the known providers has its own "
        f"credential set.{detail} Export one of: "
        + "; ".join(f"{p}: {'/'.join(PROVIDERS[p]['env'])}" for p in AUTO_ORDER if PROVIDERS[p]["env"])
        + ". Precedence: " + " > ".join(PRECEDENCE) + ".")


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

_URL_CRED_RE = re.compile(r"([?&](?:key|api[_-]?key|access_token|token)=)[^&\s]+", re.I)


def probe(provider: str, base_url: str = "", *, timeout: float = 5.0) -> tuple[bool, str]:
    """Is ``provider``'s endpoint reachable with ``provider``'s OWN credential?

    Returns ``(ok, reason)``. Never raises, never returns a credential value.

    Wrong-endpoint safety: the URL, the auth header shape, and the credential env var
    are all read from the SAME ``PROVIDERS[provider]`` row and from nothing else, in
    this one function. There is no code path that pairs provider A's credential with
    provider B's URL — a caller-supplied ``base_url`` is only honoured when it is
    already the resolved base URL for this same provider (``_resolve_base_url``), and
    an unknown provider is refused before any request is made.
    """
    if provider not in PROVIDERS:
        return False, f"unknown provider {provider!r}"
    row = PROVIDERS[provider]
    cred_env = _scoped_credential_env(provider)
    if not cred_env:
        return False, f"no {provider} credential ({'/'.join(row['env']) or 'n/a'}) set"
    url = (base_url or _resolve_base_url(provider, {}, {})).rstrip("/")
    if not url:
        return False, f"no base URL for {provider} (set {row['base_url_env']})"
    if not url.startswith(("http://", "https://")):
        return False, f"base URL for {provider} is not http(s)"

    import urllib.error
    import urllib.request

    hdr_name, hdr_tmpl = row["header"]
    req = urllib.request.Request(url + row["probe_path"], method="GET")
    if hdr_name:
        # The only place a credential value is ever read. It goes into a header on a
        # request to THIS provider's own base URL, and is never echoed back out.
        req.add_header(hdr_name, hdr_tmpl.format(cred=os.environ[cred_env]))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:                       # reached it, refused us
        return False, _safe_reason(f"HTTP {e.code}")
    except Exception as e:                                    # DNS/TLS/timeout/...
        return False, _safe_reason(f"{type(e).__name__}: {e}")


def _safe_reason(text: str) -> str:
    """Scrub a probe failure reason before it can reach a log or an artifact.

    A library exception routinely echoes the URL it failed on, so this is the main way
    a custom endpoint would escape into a transcript. Order: mask credential query
    params, replace non-public URLs with ``<custom>`` (which also drops any userinfo),
    then run the repo's shared ``dashboard.redact`` so this path obeys exactly the same
    rules as run artifacts.
    """
    scrubbed = safe_urls_in_text(_URL_CRED_RE.sub(r"\1«redacted»", str(text)))
    return redact(scrubbed)[:300]


def describe(res: Resolved) -> str:
    """One-line, secret-free summary for the run transcript.

    Prints the *source* of a custom base URL rather than its value — that is the part
    that helps someone debug precedence, and it names no infrastructure.
    """
    who = f"{res.credential_env} (present)" if res.credential_present else "no credential"
    url = res.base_url_display or "(provider default)"
    if url == CUSTOM_URL:
        url = f"{CUSTOM_URL} (from {res.base_url_source or 'config'})"
    return (f"provider: {res.provider or 'unresolved'} | credential: {who} | "
            f"base_url: {url} | {res.reason}")
