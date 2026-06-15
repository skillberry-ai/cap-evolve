"""tools: by default the FULL action set is allowed (docs, schema, code, add/compose, remove)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract


def main() -> int:
    report = {"skill": "tools", "ok": False, "problems": [], "notes": []}
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d)
        (cap / "tools.json").write_text(json.dumps({"tools": [
            {"name": "search", "description": "Search the web.",
             "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
             "examples": ["search(q='weather')"]},
        ]}), encoding="utf-8")  # no policy.json -> default (full) policy

        rep = abstract.apply(cap, [
            {"tool": "search", "kind": "schema",
             "value": {"type": "object", "properties": {"q": {"type": "string"}, "n": {"type": "integer"}}}},
            {"tool": "search", "kind": "code", "value": "def search(q, n=10): ..."},
            {"kind": "compose", "value": {"name": "search_top", "description": "search then top-n",
                                          "code": "def search_top(q): return search(q, 1)"}},
        ])
        if rep["refused"]:
            report["problems"].append(f"full policy refused allowed edits: {rep['refused']}")
        if "schema:search" not in rep["changed"] or not any(c.startswith("compose") for c in rep["changed"]):
            report["problems"].append(f"expected schema+compose edits applied, got {rep['changed']}")
        v = abstract.validate(cap)
        if not v["ok"]:
            report["problems"].append(f"validate failed: {v['problems']}")
        report["notes"].append("full action set (schema/code/compose) allowed by default")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
