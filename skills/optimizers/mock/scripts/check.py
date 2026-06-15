"""Smoke-test the mock optimizer's edit engine deterministically."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from run import apply_edits


def main() -> int:
    report = {"skill": "mock", "ok": False, "problems": [], "notes": []}
    with tempfile.TemporaryDirectory() as d:
        wd = Path(d)
        (wd / "prompt.txt").write_text("hello", encoding="utf-8")
        a1 = apply_edits(wd, [{"file": "prompt.txt", "op": "ensure_contains", "text": " world"}])
        a2 = apply_edits(wd, [{"file": "prompt.txt", "op": "ensure_contains", "text": " world"}])
        content = (wd / "prompt.txt").read_text(encoding="utf-8")
        if content != "hello world":
            report["problems"].append(f"ensure_contains produced {content!r}")
        if not a1[0]["changed"]:
            report["problems"].append("first ensure_contains should change the file")
        if a2[0]["changed"]:
            report["problems"].append("second ensure_contains should be idempotent (no change)")
        report["notes"].append("edit engine deterministic + idempotent")
    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
