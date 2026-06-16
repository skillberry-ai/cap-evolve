"""claude-code optimizer — use Claude Code headless as the edit proposer.

Invokes the `claude` CLI in print/headless mode with cwd set to the candidate
workdir, so Claude reads INSTRUCTIONS.md and edits the capability files in place.

Invocation (Claude Code headless):
    claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]
run with cwd=<workdir>. `--permission-mode acceptEdits` lets it write files
without prompting; `-p/--print` runs non-interactively and exits.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401


def build_cmd(instructions: str, model: str | None) -> list[str]:
    cmd = ["claude", "-p", instructions, "--permission-mode", "acceptEdits"]
    if model:
        cmd += ["--model", model]
    return cmd


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="claude-code optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=os.environ.get("CAPEVOLVE_OPTIMIZER_MODEL") or None)
    args = p.parse_args(argv)

    if shutil.which("claude") is None:
        print(json.dumps({"optimizer": "claude-code", "error":
              "the `claude` CLI is not on PATH. Install Claude Code, or use the "
              "`generic` optimizer / `mock` for tests."}))
        return 2

    instructions = Path(args.prompt).read_text(encoding="utf-8")
    cmd = build_cmd(instructions, args.model)
    proc = subprocess.run(cmd, cwd=args.workdir, capture_output=True, text=True)
    print(json.dumps({"optimizer": "claude-code", "returncode": proc.returncode,
                      "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
