"""mcp-tool capability — optimize an MCP toolset whose SERVER is external.

The wire schema and tool implementation belong to the MCP server, not us, so the
DEFAULT_POLICY allows only the safe subset: reword descriptions, tweak documented
params, edit examples, and add/remove tools — but NOT ``schema`` or ``code``
edits (changing the wire contract of a server you do not own would break it).
(Contrast ``tools``, which owns its code and allows the full set.)

The artifact is ``tools.json``; the materialize/apply/validate mechanics are
shared in ``cap_evolve.tool_surface`` — this module only declares the policy.
"""

from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import tool_surface

# External server → documentation + add/remove only (no schema/code).
DEFAULT_POLICY = {"allow": ["description", "params", "examples", "add", "remove"]}


def load_policy(capability_dir: Path) -> dict:
    return tool_surface.load_policy(capability_dir, DEFAULT_POLICY)


def materialize(capability_dir: Path) -> dict:
    return tool_surface.materialize(capability_dir)


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    return tool_surface.apply(capability_dir, DEFAULT_POLICY, edits)


def validate(capability_dir: Path) -> dict:
    return tool_surface.validate(capability_dir)
