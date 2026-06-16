"""generic optimizer — drive ANY shell-invokable agent as the edit proposer.

The loop calls this with ``--workdir`` (a copy of the candidate) and ``--prompt``
(INSTRUCTIONS.md). This script in turn invokes whatever agent command you set in
``CAPEVOLVE_OPTIMIZER_CMD`` (a template with ``{workdir}`` and ``{prompt}``), with cwd
set to the workdir so the agent edits files in place. This is the escape hatch
that makes "any optimizer" literally true — if your agent has a CLI, it plugs in.

Example:
    export CAPEVOLVE_OPTIMIZER_CMD='my-agent edit --dir {workdir} --instructions {prompt}'
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="generic optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--cmd", default=None, help="override CAPEVOLVE_OPTIMIZER_CMD")
    args = p.parse_args(argv)

    template = args.cmd or os.environ.get("CAPEVOLVE_OPTIMIZER_CMD")
    if not template:
        print(json.dumps({"optimizer": "generic", "error":
              "set CAPEVOLVE_OPTIMIZER_CMD (or --cmd) to your agent's edit command "
              "with {workdir} and {prompt} placeholders"}))
        return 2
    cmd = [c.replace("{workdir}", args.workdir).replace("{prompt}", args.prompt)
           for c in shlex.split(template)]
    proc = subprocess.run(cmd, cwd=args.workdir, capture_output=True, text=True)
    out = {"optimizer": "generic", "cmd": cmd, "returncode": proc.returncode,
           "stdout_tail": proc.stdout[-500:], "stderr_tail": proc.stderr[-500:]}
    print(json.dumps(out))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
