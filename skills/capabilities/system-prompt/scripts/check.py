"""Round-trip materialize → apply → validate on a temp prompt artifact."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract


def main() -> int:
    report = {"skill": "system-prompt", "ok": False, "problems": [], "notes": []}
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d)
        (cap / "prompt.txt").write_text("You are helpful.", encoding="utf-8")
        parts = abstract.materialize(cap)
        if "prompt.txt" not in parts:
            report["problems"].append("materialize did not read prompt.txt")
        rep = abstract.apply(cap, [{"file": "prompt.txt", "op": "ensure_contains", "text": " Be concise."}])
        if "prompt.txt" not in rep["changed"]:
            report["problems"].append("apply did not record a change")
        v = abstract.validate(cap)
        if not v["ok"]:
            report["problems"].append(f"validate failed: {v['problems']}")
        report["notes"].append("materialize/apply/validate round-trip ok")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
