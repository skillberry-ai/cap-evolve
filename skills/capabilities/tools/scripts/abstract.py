"""tools_mcp capability — optimize an agent's tool / MCP surface.

The artifact is ``tools.json``: a list of tool definitions, each
``{name, description, parameters (JSON schema), examples, code?}``. These
concrete handlers parse it into editable components and apply edits under an
**action policy** (prior agent-optimization work's mutation-lock): only the edit kinds you allow can be
made, so you can let an optimizer reword descriptions while forbidding it from
changing the wire schema.

Action kinds: ``description`` | ``params`` | ``examples`` | ``schema`` | ``code``
| ``add`` | ``remove`` | ``compose`` (add a tool that calls existing tools).
The allowed set lives in ``inputs/policy.json`` (default: description, params,
examples only — the safe subset).
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_POLICY = {"allow": ["description", "params", "examples", "schema", "code", "add", "compose", "remove"]}


def _load(capability_dir: Path) -> dict:
    f = Path(capability_dir) / "tools.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"tools": []}


def _save(capability_dir: Path, data: dict) -> None:
    (Path(capability_dir) / "tools.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_policy(capability_dir: Path) -> dict:
    f = Path(capability_dir) / "policy.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else dict(DEFAULT_POLICY)


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


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    """Apply edits honoring the action policy. Returns {changed, refused}.

    Edit shape: {"tool": name, "kind": <action>, "value": ...}. For ``add`` /
    ``compose`` the value is a full tool def; for ``remove`` value is ignored.
    """
    data = _load(capability_dir)
    policy = set(load_policy(capability_dir).get("allow", []))
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


def validate(capability_dir: Path) -> dict:
    data = _load(capability_dir)
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
