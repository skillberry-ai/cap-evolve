"""mcp-tool: by default ONLY docs + add/remove are allowed; schema/code are refused."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract


def main() -> int:
    report = {"skill": "mcp-tool", "ok": False, "problems": [], "notes": []}
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d)
        (cap / "tools.json").write_text(json.dumps({"tools": [
            {"name": "lookup", "description": "Look up a record.",
             "parameters": {"type": "object", "properties": {"id": {"type": "string"}}}},
        ]}), encoding="utf-8")  # no policy.json -> default (restricted) policy

        # docs + add/remove allowed
        ok_edits = abstract.apply(cap, [
            {"tool": "lookup", "kind": "description", "value": "Look up a customer record by id."},
            {"kind": "add", "value": {"name": "ping", "description": "health check",
                                      "parameters": {"type": "object"}}},
        ])
        if ok_edits["refused"]:
            report["problems"].append(f"docs/add wrongly refused: {ok_edits['refused']}")

        # schema + code are NOT permitted for MCP tools (served by an external server)
        bad = abstract.apply(cap, [
            {"tool": "lookup", "kind": "schema", "value": {}},
            {"tool": "lookup", "kind": "code", "value": "def lookup(): ..."},
        ])
        if len(bad["refused"]) != 2:
            report["problems"].append(f"schema/code should both be refused, got {bad}")
        v = abstract.validate(cap)
        if not v["ok"]:
            report["problems"].append(f"validate failed: {v['problems']}")
        report["notes"].append("docs+add/remove allowed; schema/code refused by default")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
