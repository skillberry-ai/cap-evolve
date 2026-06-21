"""Contract: run-optimizer resolves the registry, the mock row is offline and
applies a real edit, and command-building drops an empty ``--model`` group.

Reports "CLI present: yes/no" per optimizer (mock is always present because it
runs a shipped python helper, not a network CLI) rather than passing
unconditionally.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run


def main() -> int:
    c = Checker("run-optimizer")
    run = import_run()
    c.require_main(run)

    reg = run.load_registry()
    c.check("mock" in reg, "registry missing the offline `mock` row",
            note=f"registry rows: {sorted(reg)}")
    c.check(str(reg.get("mock", {}).get("offline", "")).lower() == "true",
            "mock row must be offline:true (zero-API)")

    # build_command drops `-m {model}` when no model is set, keeps it when set.
    cc = reg.get("claude-code", {}).get("command_template", "")
    no_model = run.build_command(cc, workdir="/w", prompt="/p", prompt_text="hi",
                                 model=None, self_dir="/s")
    with_model = run.build_command(cc, workdir="/w", prompt="/p", prompt_text="hi",
                                   model="m1", self_dir="/s")
    c.check("--model" not in no_model and "{model}" not in " ".join(no_model),
            f"empty model group not dropped: {no_model}")
    c.check("--model" in with_model and "m1" in with_model,
            f"model not injected when set: {with_model}")

    # mock actually edits a file in place (offline), proving the loop can run with no API.
    mock_apply = __import__("_mock_apply")
    with tempfile.TemporaryDirectory() as d:
        wd = Path(d)
        (wd / "prompt.txt").write_text("hello", encoding="utf-8")
        a1 = mock_apply.apply_edits(wd, [{"file": "prompt.txt", "op": "ensure_contains", "text": " world"}])
        a2 = mock_apply.apply_edits(wd, [{"file": "prompt.txt", "op": "ensure_contains", "text": " world"}])
        c.check((wd / "prompt.txt").read_text() == "hello world", "mock edit wrong result")
        c.check(a1[0]["changed"] and not a2[0]["changed"],
                "mock ensure_contains not idempotent", note="mock offline editor is deterministic")

    # CLI-present report (informational, never fails — mock is the offline guarantee).
    present = {}
    for name, row in reg.items():
        if str(row.get("offline", "")).lower() == "true":
            present[name] = True
            continue
        tmpl = run.build_command(row.get("command_template", ""), workdir="/w", prompt="/p",
                                 prompt_text="x", model=None, self_dir="/s")
        present[name] = bool(tmpl) and shutil.which(tmpl[0]) is not None
    c.note("CLI present: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in present.items()))

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
