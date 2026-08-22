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
        if "warnings" not in v:
            report["problems"].append("validate omitted 'warnings' on the non-empty branch")
        report["notes"].append("materialize/apply/validate round-trip ok")

        # The two ops that can destroy content, plus the unknown-op guard.
        abstract.apply(cap, [{"file": "prompt.txt", "op": "append", "text": "\nCite sources.\n"}])
        if "Cite sources." not in (cap / "prompt.txt").read_text(encoding="utf-8"):
            report["problems"].append("apply op=append did not concatenate")
        rep = abstract.apply(cap, [{"file": "prompt.txt", "op": "set", "text": "Be helpful.\n"}])
        if (cap / "prompt.txt").read_text(encoding="utf-8") != "Be helpful.\n":
            report["problems"].append("apply op=set did not replace the file")
        if not rep["warnings"]:
            report["problems"].append("apply op=set dropped rule-bearing lines without warning")
        report["notes"].append("set/append ops behave; a rule-dropping set is flagged")
        try:
            abstract.apply(cap, [{"file": "prompt.txt", "op": "nope", "text": "x"}])
        except ValueError:
            pass
        else:
            report["problems"].append("apply accepted an unknown op")

        # validate against a baseline sees the loss the edit above introduced.
        vb = abstract.validate(cap, baseline={"prompt.txt": "Rule one.\nRule two.\nRule three.\n"})
        if not vb["warnings"]:
            report["problems"].append("validate(baseline=) missed a rule-bearing-line drop")

    # The empty-seed branch is a valid starting state, not a failure.
    with tempfile.TemporaryDirectory() as d:
        ve = abstract.validate(Path(d))
        if not (ve["ok"] and ve.get("empty") and ve["warnings"] == []):
            report["problems"].append(f"validate on an empty dir should be ok/empty: {ve}")
        report["notes"].append("empty seed validates as a valid starting state")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
