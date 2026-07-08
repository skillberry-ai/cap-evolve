"""tools capability — optimize an agent's OWN tool surface (the full action set).

This capability owns the tool code, so its DEFAULT_POLICY allows every edit kind:
reword descriptions, change parameter schema, edit tool ``code``, compose new
tools from existing ones, and add/remove tools. (Contrast ``mcp-tool``, whose
server is external and so forbids schema/code edits.)

The artifact is ``tools.json``; the materialize/apply/validate mechanics are
shared in ``cap_evolve.tool_surface`` — this module only declares the policy.
"""

from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import tool_surface

# tools owns its code → the FULL action set is allowed by default.
DEFAULT_POLICY = {"allow": ["description", "params", "examples", "schema", "code",
                            "add", "compose", "remove"]}


def load_policy(capability_dir: Path) -> dict:
    return tool_surface.load_policy(capability_dir, DEFAULT_POLICY)


def materialize(capability_dir: Path) -> dict:
    return tool_surface.materialize(capability_dir)


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    return tool_surface.apply(capability_dir, DEFAULT_POLICY, edits)


def is_empty(capability_dir: Path) -> bool:
    return tool_surface.is_empty(capability_dir)


def validate(capability_dir: Path) -> dict:
    return tool_surface.validate(capability_dir)
