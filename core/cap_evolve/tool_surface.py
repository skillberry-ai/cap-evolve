"""Shared tool-surface materialize / apply / validate for the tool capabilities.

``capabilities/tools`` and ``capabilities/mcp-tool`` optimize the same artifact —
``tools.json`` (a list of tool defs ``{name, description, parameters, examples,
code?}``) — and differ ONLY in their **action policy**: which edit kinds an
optimizer may make. The 108 duplicated lines that used to live in each skill's
``abstract.py`` (with a docstring that was false for one of them) now live here
once; each capability's ``abstract.py`` is a thin wrapper that sets its
``DEFAULT_POLICY`` and re-exports these functions.

Action kinds: ``description`` | ``params`` | ``examples`` | ``schema`` | ``code``
| ``add`` | ``remove`` | ``compose`` (add a tool that calls existing tools).
A capability whose server is external (mcp-tool) allows only the documentation +
add/remove subset; a capability that owns its tool code (tools) allows the full
set. The effective policy is ``inputs/policy.json`` if present, else the
capability's ``DEFAULT_POLICY``.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load(capability_dir: Path) -> dict:
    f = Path(capability_dir) / "tools.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"tools": []}


def _save(capability_dir: Path, data: dict) -> None:
    (Path(capability_dir) / "tools.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_policy(capability_dir: Path, default_policy: dict) -> dict:
    """``inputs/policy.json`` if present (it overrides), else the capability default."""
    f = Path(capability_dir) / "policy.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else dict(default_policy)


def materialize(capability_dir: Path) -> dict:
    """Flatten the tool surface into named text components for a text optimizer."""
    data = _load(capability_dir)
    parts = {}
    for t in data.get("tools", []):
        n = t["name"]
        parts[f"tool.{n}.description"] = t.get("description", "")
        parts[f"tool.{n}.parameters"] = json.dumps(t.get("parameters", {}), indent=2)
        parts[f"tool.{n}.examples"] = "\n".join(t.get("examples", []))
    return parts


def apply(capability_dir: Path, default_policy: dict, edits: list[dict] | None = None) -> dict:
    """Apply edits honoring the action policy. Returns {changed, refused}.

    Edit shape: {"tool": name, "kind": <action>, "value": ...}. For ``add`` /
    ``compose`` the value is a full tool def; for ``remove`` value is ignored.
    Edit kinds outside the policy are refused (not applied).
    """
    data = _load(capability_dir)
    policy = set(load_policy(capability_dir, default_policy).get("allow", []))
    by_name = {t["name"]: t for t in data.get("tools", [])}
    report = {"changed": [], "refused": []}

    for e in edits or []:
        kind = e.get("kind")
        if kind not in policy:
            report["refused"].append({"edit": e, "reason": f"action '{kind}' not allowed by policy"})
            continue
        name = e.get("tool")
        val = e.get("value")
        if kind in ("add", "compose"):
            data.setdefault("tools", []).append(val)
            report["changed"].append(f"{kind}:{val.get('name')}")
        elif kind == "remove":
            data["tools"] = [t for t in data.get("tools", []) if t["name"] != name]
            report["changed"].append(f"remove:{name}")
        elif name in by_name:
            tool = by_name[name]
            if kind == "description":
                tool["description"] = val
            elif kind == "params":
                tool.setdefault("parameters", {}).update(val if isinstance(val, dict) else {})
            elif kind == "examples":
                tool["examples"] = val
            elif kind == "schema":
                tool["parameters"] = val
            elif kind == "code":
                tool["code"] = val
            report["changed"].append(f"{kind}:{name}")
        else:
            report["refused"].append({"edit": e, "reason": f"unknown tool '{name}'"})
    _save(capability_dir, data)
    return report


def is_empty(capability_dir: Path) -> bool:
    """Return True when the capability directory has no tool definitions yet."""
    data = _load(capability_dir)
    return not data.get("tools")


def validate(capability_dir: Path) -> dict:
    """Validate the tool surface. An empty capability (no tools.json or empty tools
    list) is accepted as a valid starting state so the optimizer can create initial
    tools from failing trajectories."""
    data = _load(capability_dir)
    if not data.get("tools"):
        return {"ok": True, "empty": True, "tools": [], "problems": []}
    problems = []
    names = set()
    for t in data.get("tools", []):
        if "name" not in t:
            problems.append("a tool is missing 'name'")
            continue
        if t["name"] in names:
            problems.append(f"duplicate tool name: {t['name']}")
        names.add(t["name"])
        if not t.get("description", "").strip():
            problems.append(f"tool {t['name']} has an empty description")
        if not isinstance(t.get("parameters", {}), dict):
            problems.append(f"tool {t['name']} parameters must be a JSON-schema object")
    return {"ok": not problems, "tools": sorted(names), "problems": problems}
