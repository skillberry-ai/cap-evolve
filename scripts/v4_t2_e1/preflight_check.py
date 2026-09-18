#!/usr/bin/env python3
"""Pre-flight checks v4_t2_e1's per-task runner makes before committing a
task's budget to a run.

Two independent gates:

  * installed_cli_supports_stop_at_reward() — the globally-installed
    `cap-evolve` tool matches this worktree's core/ (specifically, that it
    supports --stop-at-reward, added by PR #415 / commit d1275b32a).
  * stack_is_healthy() — the 5 shared MCP simulation services and parsec-live
    itself are actually accepting connections.
"""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
REMEDY_CMD = f"uv tool install --force {CORE_DIR}"

#: The shared local stack every v4_t2_e1 trial depends on. Port assignments
#: mirror adapter.py's MCP_PORTS (and install_seeds.py's SERVICE_PORTS) plus
#: parsec-live's own :8000.
STACK_PORTS = {
    "parsec-live": 8000,
    "PLATFORM_MCP": 8086,
    "GITHUB_MCP": 8087,
    "ICINGA_MCP": 8088,
    "COST_MCP": 8089,
    "CLOUD_MCP": 8090,
}


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


def stack_is_healthy() -> tuple[bool, list[str]]:
    """Is every service a v4_t2_e1 trial needs accepting connections?

    Returns ``(healthy, [names of unreachable services])``.

    A TCP connect, deliberately — not an HTTP health probe. The point is to
    catch the cheap, common failure (a container exited, the podman machine is
    down, a port was never published) before a task's whole budget — up to 3
    iterations x 5 trials at up to $50 — burns against a stack that scores
    every trial 0.0. Those zeros are indistinguishable from a real capability
    failure once they are in the run record, which is what makes this worth
    checking up front rather than diagnosing afterwards.
    """
    unreachable: list[str] = []
    for name, port in STACK_PORTS.items():
        try:
            socket.create_connection(("127.0.0.1", port), timeout=2).close()
        except OSError:
            unreachable.append(name)
    return (not unreachable, unreachable)


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
