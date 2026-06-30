"""IBM Anthropic-compatible gateway wiring for the in-sandbox claude agent.

The agent under test (BenchFlow's ``claude`` agent = Claude Code via ACP) runs in
a Docker container and must reach the IBM-internal Anthropic-compatible LiteLLM
gateway. We never hardcode the token: it is read from the repo-root ``.env`` (same
loader pattern as ``examples/tau2_airline/adapters/rits.py`` — walk parents,
``setdefault``, no python-dotenv dep) and PROPAGATED into the sandbox with
BenchFlow's ``--agent-env KEY=VALUE`` flags.

Endpoint resolution is trivial here (the gateway is a fixed base URL + bearer
token), so unlike RITS there is no inference-info lookup — but like RITS this does
NO network at import time, so ``cap-evolve check`` stays offline.
"""

from __future__ import annotations

import os
from pathlib import Path

# The Anthropic-compatible env var names the in-sandbox claude agent honors.
BASE_URL_VAR = "ANTHROPIC_BASE_URL"
AUTH_TOKEN_VAR = "ANTHROPIC_AUTH_TOKEN"


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
                # Best-effort .env load: a malformed/unreadable .env is intentionally
                # non-fatal here so import never fails on the filesystem. A genuinely
                # missing credential is reported later, by gateway_env() at call time.
                pass
            break


def gateway_env() -> dict[str, str]:
    """Return {ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN} for the sandboxed agent.

    Reads the repo-root .env first (without overwriting anything already in the
    process env), then pulls the two vars. Raises only when actually needed for a
    real rollout — ``cap-evolve check`` never calls this.
    """
    _load_env()
    base = os.environ.get(BASE_URL_VAR)
    token = os.environ.get(AUTH_TOKEN_VAR)
    missing = [v for v, x in ((BASE_URL_VAR, base), (AUTH_TOKEN_VAR, token)) if not x]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Put them in the repo-root .env "
            "(copied from ~/.claude/settings.json's env block) — never hardcode the token."
        )
    return {BASE_URL_VAR: base, AUTH_TOKEN_VAR: token}
