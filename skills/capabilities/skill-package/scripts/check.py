"""Round-trip materialize -> apply -> validate on a sample skill package, and
assert the authoring-rule checks fire."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract


def main() -> int:
    report = {"skill": "skill-package", "ok": False, "problems": [], "notes": []}
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d)
        (cap / "SKILL.md").write_text(
            "---\nname: demo-skill\n"
            "description: Do a thing. Use when the user wants the thing done.\n---\n"
            "# Demo\nBody.\n", encoding="utf-8")
        parts = abstract.materialize(cap)
        if "SKILL.md" not in parts:
            report["problems"].append("materialize missed SKILL.md")
        v = abstract.validate(cap)
        if not v["ok"]:
            report["problems"].append(f"valid skill rejected: {v['problems']}")

        # an invalid name must be caught
        (cap / "SKILL.md").write_text(
            "---\nname: Bad_Name_With_Caps\ndescription: x\n---\n# x\n", encoding="utf-8")
        v2 = abstract.validate(cap)
        if v2["ok"]:
            report["problems"].append("invalid name not rejected")

        # apply edit works
        abstract.apply(cap, [{"file": "references/extra.md", "op": "set", "text": "# Extra\n"}])
        if not (cap / "references" / "extra.md").exists():
            report["problems"].append("apply did not write a reference file")
        report["notes"].append("materialize/apply/validate + rule checks ok")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
