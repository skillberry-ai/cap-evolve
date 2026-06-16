"""openclaw optimizer — drive OpenClaw as the edit proposer (configurable).

OpenClaw's headless CLI flags are less standardized than claude/codex/gemini, so
this skill is a thin, documented wrapper: set ``CAPEVOLVE_OPENCLAW_CMD`` to OpenClaw's
non-interactive edit command (with ``{workdir}`` and ``{prompt}`` placeholders).
Defaults to a best-guess ``openclaw run`` form that you should verify against your
installed version.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

DEFAULT_CMD = 'openclaw run --workspace {workdir} "{prompt_text}"'


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="openclaw optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    args = p.parse_args(argv)

    template = os.environ.get("CAPEVOLVE_OPENCLAW_CMD", DEFAULT_CMD)
    instr = Path(args.prompt).read_text(encoding="utf-8")
    cmd = [c.replace("{workdir}", args.workdir).replace("{prompt}", args.prompt)
            .replace("{prompt_text}", instr) for c in shlex.split(template)]
    if shutil.which(cmd[0]) is None:
        print(json.dumps({"optimizer": "openclaw", "error":
              f"`{cmd[0]}` not on PATH. Set CAPEVOLVE_OPENCLAW_CMD to your OpenClaw "
              "non-interactive edit command, or use `generic`."}))
        return 2
    proc = subprocess.run(cmd, cwd=args.workdir, capture_output=True, text=True)
    print(json.dumps({"optimizer": "openclaw", "cmd": cmd[0], "returncode": proc.returncode,
                      "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
