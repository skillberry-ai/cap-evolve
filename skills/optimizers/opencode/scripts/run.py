"""opencode optimizer — opencode headless as the edit proposer.

Invocation (verified against opencode.ai/docs/cli):
    opencode run --dangerously-skip-permissions "<instructions>"
run with cwd=<workdir>. `opencode run` is the headless mode (bare `opencode` is
the TUI); `-m provider/model` pins the model.
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
    cmd = ["opencode", "run", "--dangerously-skip-permissions"]
    if model:
        cmd += ["-m", model]
    cmd += [instructions]
    return cmd


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="opencode optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=os.environ.get("ACAPO_OPTIMIZER_MODEL") or None)
    args = p.parse_args(argv)
    if shutil.which("opencode") is None:
        print(json.dumps({"optimizer": "opencode", "error": "the `opencode` CLI is not on PATH"}))
        return 2
    instr = Path(args.prompt).read_text(encoding="utf-8")
    proc = subprocess.run(build_cmd(instr, args.model), cwd=args.workdir,
                          capture_output=True, text=True)
    print(json.dumps({"optimizer": "opencode", "returncode": proc.returncode,
                      "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
