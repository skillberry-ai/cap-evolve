#!/usr/bin/env python3
"""Pre-flight check this arm's per-task runner makes before committing a
task's budget to a run.

Only one gate here, unlike v4_t2_e1's two:

  * stack_is_healthy() -- the 5 shared MCP simulation services and
    parsec-live itself are actually accepting connections.

v4_t2_e1's other gate, installed_cli_supports_stop_at_reward(), checked the
GLOBALLY-INSTALLED `cap-evolve` uv tool, because v4_t2_e1's run_one_task.py
shells out to that tool (`cap-evolve run ...`). this arm's run_one_task.py
never does that -- it invokes skills/phases/baseline/scripts/run.py directly
via sys.executable, and that script's own _bootstrap.py resolves cap_evolve
from THIS worktree's own core/ (it walks up from its own file location, and
only defers to a global install if CAPEVOLVE_CORE is explicitly set). So
there is no "is the installed tool stale" question to ask here at all.
"""
from __future__ import annotations

import socket

#: The shared local stack every trial depends on. Same ports as
#: v4_t2_e1's preflight_check.py (they gate the same physical stack).
STACK_PORTS = {
    "parsec-live": 8000,
    "PLATFORM_MCP": 8086,
    "GITHUB_MCP": 8087,
    "ICINGA_MCP": 8088,
    "COST_MCP": 8089,
    "CLOUD_MCP": 8090,
}


def stack_is_healthy() -> tuple[bool, list[str]]:
    """Is every service a trial needs accepting connections?

    Returns ``(healthy, [names of unreachable services])``.

    A TCP connect, deliberately -- not an HTTP health probe. The point is to
    catch the cheap, common failure (a container exited, the podman machine
    is down, a port was never published) before a task's 5-trial baseline
    eval burns against a stack that scores every trial 0.0. Those zeros are
    indistinguishable from a real capability failure once they are in the
    run record, which is what makes this worth checking up front.
    """
    unreachable: list[str] = []
    for name, port in STACK_PORTS.items():
        try:
            socket.create_connection(("127.0.0.1", port), timeout=2).close()
        except OSError:
            unreachable.append(name)
    return (not unreachable, unreachable)


def main() -> int:
    healthy, unreachable = stack_is_healthy()
    if healthy:
        print("OK: simulation stack is healthy.")
        return 0
    print(f"UNHEALTHY: unreachable services: {', '.join(unreachable)}")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
