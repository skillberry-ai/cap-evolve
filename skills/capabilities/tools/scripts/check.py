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
            # remove-with-replacement: search_top subsumes search, so drop the primitive.
            {"tool": "search", "kind": "remove"},
        ])
        if rep["refused"]:
            report["problems"].append(f"full policy refused allowed edits: {rep['refused']}")
        if "schema:search" not in rep["changed"] or not any(c.startswith("compose") for c in rep["changed"]):
            report["problems"].append(f"expected schema+compose edits applied, got {rep['changed']}")
        if "remove:search" not in rep["changed"]:
            report["problems"].append(f"expected remove:search applied, got {rep['changed']}")
        names = [t.get("name") for t in json.loads((cap / "tools.json").read_text())["tools"]]
        if names != ["search_top"]:
            report["problems"].append(f"after compose+remove expected ['search_top'], got {names}")
        v = abstract.validate(cap)
        if not v["ok"]:
            report["problems"].append(f"validate failed: {v['problems']}")
        report["notes"].append("full action set (schema/code/compose/remove) allowed by default")

        # A tightened policy must REFUSE, not silently drop or silently apply.
        (cap / "policy.json").write_text(
            json.dumps({"allow": ["description"]}), encoding="utf-8")
        rep2 = abstract.apply(cap, [
            {"tool": "search_top", "kind": "description", "value": "Search and return the top hit."},
            {"tool": "search_top", "kind": "code", "value": "def search_top(q): return 1"},
        ])
        if not rep2["refused"]:
            report["problems"].append("tightened policy did not refuse a 'code' edit")
        if "description:search_top" not in rep2["changed"]:
            report["problems"].append(f"tightened policy dropped an allowed edit: {rep2['changed']}")
        report["notes"].append("tightened policy refuses disallowed kinds and reports them")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
