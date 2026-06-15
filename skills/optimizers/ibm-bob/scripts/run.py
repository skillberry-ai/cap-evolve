"""ibm-bob optimizer — drive IBM Bob Shell (the `bob` CLI) as the edit proposer.

Runs Bob non-interactively in the candidate working directory so it reads the
INSTRUCTIONS and edits the capability files in place:

    bob --accept-license --yolo --chat-mode code "<instructions>"     # cwd = workdir

- `--yolo` (a.k.a. `--approval-mode yolo`) auto-approves all actions so Bob can
  write files (the workdir is a throwaway candidate copy).
- `--accept-license` accepts the IBM license on first run (needed in fresh/CI envs).
- The positional prompt is the non-interactive one-shot form (`-p/--prompt` is
  deprecated upstream).
- Auth: Bob reads `BOBSHELL_API_KEY`. This script populates it from
  `BOBSHELL_API_KEY` → `BOB_API_KEY` (env or the repo `.env`).

Install Bob Shell if it isn't on PATH:
    curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash -s -- --package-manager npm
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


def _load_bob_key() -> str | None:
    """BOBSHELL_API_KEY, else BOB_API_KEY (env or the nearest .env up the tree)."""
    for k in ("BOBSHELL_API_KEY", "BOB_API_KEY"):
        if os.environ.get(k):
            return os.environ[k]
    here = Path(__file__).resolve()
    for parent in here.parents:
        env = parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    name, val = line.split("=", 1)
                    if name.strip() in ("BOBSHELL_API_KEY", "BOB_API_KEY"):
                        return val.strip().strip('"').strip("'")
            break
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ibm-bob optimizer")
    p.add_argument("--workdir", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", default=os.environ.get("ACAPO_OPTIMIZER_MODEL") or None)
    args = p.parse_args(argv)

    if shutil.which("bob") is None:
        print(json.dumps({"optimizer": "ibm-bob", "error":
              "the `bob` CLI is not on PATH. Install Bob Shell: "
              "curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash -s -- --package-manager npm"}))
        return 2

    key = _load_bob_key()
    env = dict(os.environ)
    if key:
        env["BOBSHELL_API_KEY"] = key

    instr = Path(args.prompt).read_text(encoding="utf-8")
    cmd = ["bob", "--accept-license", "--yolo", "--chat-mode", "code",
           "--hide-intermediary-output"]
    if args.model:
        cmd += ["-m", args.model]
    cmd += [instr]   # positional one-shot prompt

    proc = subprocess.run(cmd, cwd=args.workdir, capture_output=True, text=True, env=env)
    print(json.dumps({"optimizer": "ibm-bob", "returncode": proc.returncode,
                      "auth": bool(key), "stdout_tail": proc.stdout[-800:],
                      "stderr_tail": proc.stderr[-500:]}))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
