"""codex optimizer — OpenAI Codex CLI headless as the edit proposer.

Invocation (verified against developers.openai.com/codex/noninteractive):
    codex exec --sandbox workspace-write -m <model> "<instructions>"
run with cwd=<workdir> so Codex edits the candidate files in place. `codex exec`
is the non-interactive subcommand; `--full-auto` is deprecated in favor of
`--sandbox workspace-write` (file writes, no network).
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
    cmd = ["codex", "exec", "--sandbox", "workspace-write"]
    if model:
        cmd += ["-m", model]
    cmd += [instructions]
    return cmd


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="codex optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=os.environ.get("ACAPO_OPTIMIZER_MODEL") or None)
    args = p.parse_args(argv)
    if shutil.which("codex") is None:
        print(json.dumps({"optimizer": "codex", "error": "the `codex` CLI is not on PATH"}))
        return 2
    instr = Path(args.prompt).read_text(encoding="utf-8")
    proc = subprocess.run(build_cmd(instr, args.model), cwd=args.workdir,
                          capture_output=True, text=True)
    print(json.dumps({"optimizer": "codex", "returncode": proc.returncode,
                      "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
