"""gemini-cli optimizer — Google Gemini CLI headless as the edit proposer.

Invocation (verified against google-gemini/gemini-cli docs):
    gemini -p "<instructions>" --approval-mode=yolo -m <model>
run with cwd=<workdir>. `-p` forces non-interactive; `--approval-mode=yolo`
auto-approves actions (`--yolo` is deprecated in favor of it).
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
    cmd = ["gemini", "-p", instructions, "--approval-mode=yolo"]
    if model:
        cmd += ["-m", model]
    return cmd


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gemini-cli optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=os.environ.get("CAPEVOLVE_OPTIMIZER_MODEL") or None)
    args = p.parse_args(argv)
    if shutil.which("gemini") is None:
        print(json.dumps({"optimizer": "gemini-cli", "error": "the `gemini` CLI is not on PATH"}))
        return 2
    instr = Path(args.prompt).read_text(encoding="utf-8")
    proc = subprocess.run(build_cmd(instr, args.model), cwd=args.workdir,
                          capture_output=True, text=True)
    print(json.dumps({"optimizer": "gemini-cli", "returncode": proc.returncode,
                      "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
