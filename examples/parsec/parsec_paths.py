#!/usr/bin/env python3
"""Single source of truth for "which parsec checkout" (v4 or v5) and the
shared MCP port table.

Both were previously hardcoded independently in adapter.py and
scaffold_projects.py — two copies of the same PARSEC_V4N env-var-with-Mac-
fallback default. scaffold_projects.py's own comment already named the
risk: a seed snapshot gets frozen from one tree while the trials that score
it run against another, if the two copies ever drift. This module is the
fix: both files import from here instead of defining their own copy.

v5 is a separate, from-scratch benchmark checkout (not a v4 variant), so it
gets its own env var ($PARSEC_V5N) and its own resolve_v5n()/V5N_REQUIRED_MSG
rather than overloading v4's — the two trees are never meant to be read
interchangeably. The MCP port table is shared: v5 reuses the same 5-service
simulator topology v4/h4 proved, so examples/parsec/v5/'s scripts import
MCP_PORTS from here too.

There is deliberately NO machine-specific fallback path for either. A
fallback here is exactly the bug this module replaces (it was a personal Mac
path; on CCC there is no equivalent single "the" checkout to default to) —
callers that need a v4_t2_e1-shaped (or v5-shaped) operation, not just a
path, use resolve_v4n()/resolve_v5n() and get a clear RuntimeError instead
of silently resolving to the wrong tree.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Every v4_t2_e1 trial's target: the 5 harness-simulation MCP endpoints,
#: keyed by the env var name adapter.py sets before invoking `harbor run`.
#: Values are the simulator containers' PUBLISHED ports (their internal port is
#: always 8086), per the compose topology in <PARSEC_V4N>/README.md. This dict
#: is the source of truth for them in this repo; examples/parsec/ccc/parsec_stack.sh and
#: CCC_PODMAN_SETUP.md's table both point here. (_run/harness-cfg/*.yaml carry
#: the same numbers as `server.port`, but those files are Mac-local leftovers
#: that nothing on this branch reads — do not treat them as the reference.)
MCP_PORTS: dict[str, int] = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


#: One source of truth for the "you forgot to set PARSEC_V4N" wording.
#: resolve_v4n() raises it; callers that must keep their own *condition* (because
#: they branch on a module-level constant captured at import time, not on a fresh
#: read of the environment) still reuse this text rather than paraphrasing it.
V4N_REQUIRED_MSG = (
    "PARSEC_V4N environment variable is required — it must point at "
    "the root of a parsec v4 checkout (e.g. "
    ".../rhdp-parsec/v4_2026-09-16, the directory containing _run/)."
)


def resolve_v4n_or_none() -> Path | None:
    """The parsec v4 checkout root, from $PARSEC_V4N, or None if unset/blank."""
    raw = os.environ.get("PARSEC_V4N", "").strip()
    return Path(raw) if raw else None


def resolve_v4n() -> Path:
    """Like resolve_v4n_or_none(), but raises when PARSEC_V4N is unset."""
    v4n = resolve_v4n_or_none()
    if v4n is None:
        raise RuntimeError(f"{V4N_REQUIRED_MSG} Set it before running this script.")
    return v4n


#: One source of truth for the "you forgot to set PARSEC_V5N" wording.
V5N_REQUIRED_MSG = (
    "PARSEC_V5N environment variable is required — it must point at "
    "the root of a parsec v5 checkout (e.g. "
    ".../rhdp-parsec/v5_2026-10-10, the directory containing _run/)."
)


def resolve_v5n_or_none() -> Path | None:
    """The parsec v5 checkout root, from $PARSEC_V5N, or None if unset/blank."""
    raw = os.environ.get("PARSEC_V5N", "").strip()
    return Path(raw) if raw else None


def resolve_v5n() -> Path:
    """Like resolve_v5n_or_none(), but raises when PARSEC_V5N is unset."""
    v5n = resolve_v5n_or_none()
    if v5n is None:
        raise RuntimeError(f"{V5N_REQUIRED_MSG} Set it before running this script.")
    return v5n


#: One source of truth for the "you forgot to set PARSEC_V6N" wording.
V6N_REQUIRED_MSG = (
    "PARSEC_V6N environment variable is required — it must point at "
    "the root of a parsec v6 checkout (e.g. "
    ".../rhdp-parsec/v6_2026-10-16, the directory containing _run/)."
)


def resolve_v6n_or_none() -> Path | None:
    """The parsec v6 checkout root, from $PARSEC_V6N, or None if unset/blank."""
    raw = os.environ.get("PARSEC_V6N", "").strip()
    return Path(raw) if raw else None


def resolve_v6n() -> Path:
    """Like resolve_v6n_or_none(), but raises when PARSEC_V6N is unset."""
    v6n = resolve_v6n_or_none()
    if v6n is None:
        raise RuntimeError(f"{V6N_REQUIRED_MSG} Set it before running this script.")
    return v6n
