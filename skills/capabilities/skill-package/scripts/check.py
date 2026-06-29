"""Round-trip materialize -> apply -> validate on a sample skill package, and
assert the authoring-rule checks fire."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract
import token_report


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

        # an XML tag in the name is an Anthropic invariant -> hard problem
        (cap / "SKILL.md").write_text(
            "---\nname: bad-<tag>\ndescription: Do a thing. Use when needed.\n---\n# x\n",
            encoding="utf-8")
        if abstract.validate(cap)["ok"]:
            report["problems"].append("XML tag in name not rejected")

        # soft lints must fire as warnings: first person + all-caps imperative
        (cap / "SKILL.md").write_text(
            "---\nname: lint-demo\n"
            "description: I can help. ALWAYS use when the user wants it.\n---\n# x\n",
            encoding="utf-8")
        w = " ".join(abstract.validate(cap)["warnings"])
        if "third person" not in w or "over-triggers" not in w:
            report["problems"].append(f"POV/all-caps lints did not fire: {w!r}")

        # apply edit works
        abstract.apply(cap, [{"file": "references/extra.md", "op": "set", "text": "# Extra\n"}])
        if not (cap / "references" / "extra.md").exists():
            report["problems"].append("apply did not write a reference file")

        # token_report runs and reports a body budget
        tr = token_report.report(cap)
        if "body_tokens" not in tr or "over_budget" not in tr:
            report["problems"].append(f"token_report missing budget fields: {tr}")
        report["notes"].append("materialize/apply/validate + rule checks + token_report ok")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
