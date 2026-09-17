#!/usr/bin/env python3
"""Pre-flight: confirm the globally-installed `cap-evolve` tool matches this
worktree's core/ (specifically, that it supports --stop-at-reward, added by
PR #415 / commit d1275b32a). v4_t2_e1's per-task runner refuses to start a
run until this passes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
REMEDY_CMD = f"uv tool install --force {CORE_DIR}"


def installed_cli_supports_stop_at_reward() -> bool:
    try:
        result = subprocess.run(
            ["cap-evolve", "run", "--help"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"could not run `cap-evolve run --help`: {exc}", file=sys.stderr)
        return False
    return "--stop-at-reward" in result.stdout


def main() -> int:
    if installed_cli_supports_stop_at_reward():
        print("OK: installed cap-evolve supports --stop-at-reward.")
        return 0
    print(
        "STALE: the installed `cap-evolve` tool does not support --stop-at-reward.\n"
        "It is likely built from a different worktree's core/ (this has happened before —\n"
        "check its direct_url.json under the uv tool venv's dist-info).\n"
        f"Fix by reinstalling it from THIS worktree's core/:\n\n"
        f"    {REMEDY_CMD}\n\n"
        "Note: this is a machine-global `uv tool`, shared by every cap-evolve worktree on\n"
        "this machine — confirm with whoever else might be running it before doing this.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
