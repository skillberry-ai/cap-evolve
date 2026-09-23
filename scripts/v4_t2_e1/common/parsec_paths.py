#!/usr/bin/env python3
"""Single source of truth for "which parsec v4 checkout" and the shared MCP
port table.

Both were previously hardcoded independently in adapter.py and
scaffold_projects.py — two copies of the same PARSEC_V4N env-var-with-Mac-
fallback default. scaffold_projects.py's own comment already named the
risk: a seed snapshot gets frozen from one tree while the trials that score
it run against another, if the two copies ever drift. This module is the
fix: both files import from here instead of defining their own copy.

There is deliberately NO machine-specific fallback path. A fallback here is
exactly the bug this module replaces (it was a personal Mac path; on CCC
there is no equivalent single "the" checkout to default to) — callers that
need a v4_t2_e1-shaped operation, not just a path, use resolve_v4n() and get
a clear RuntimeError instead of silently resolving to the wrong tree.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Every v4_t2_e1 trial's target: the 5 harness-simulation MCP endpoints,
#: keyed by the env var name adapter.py sets before invoking `harbor run`.
#: Values mirror each service's `server.port` in _run/harness-cfg/*.yaml.
MCP_PORTS: dict[str, int] = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


def resolve_v4n_or_none() -> Path | None:
    """The parsec v4 checkout root, from $PARSEC_V4N, or None if unset/blank."""
    raw = os.environ.get("PARSEC_V4N", "").strip()
    return Path(raw) if raw else None


def resolve_v4n() -> Path:
    """Like resolve_v4n_or_none(), but raises when PARSEC_V4N is unset."""
    v4n = resolve_v4n_or_none()
    if v4n is None:
        raise RuntimeError(
            "PARSEC_V4N environment variable is required — it must point at "
            "the root of a parsec v4 checkout (e.g. "
            ".../rhdp-parsec/v4_2026-09-16, the directory containing _run/). "
            "Set it before running this script."
        )
    return v4n
