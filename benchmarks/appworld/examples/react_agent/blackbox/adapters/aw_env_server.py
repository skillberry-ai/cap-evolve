"""One AppWorld environment server (the remote REPL) for ONE trial of the blackbox approach.

    python aw_env_server.py PORT APPWORLD_ROOT

The adapter starts one per trial (appworld_tailoring.start_env_server) and stops it when the trial
ends: an AppWorld environment server holds a single world, so parallel trials need one each. The
episode worker's world attaches with ``AppWorld(..., remote_environment_url=http://127.0.0.1:PORT)``,
a constructor argument of the world: the agent stays AppWorld's stock ``SimplifiedReActCodeAgent``.

Why not ``appworld serve environment``: it binds every interface (0.0.0.0) and first kills whatever
process holds its port. This serves the same server app (``appworld.serve.environment.app``) on
127.0.0.1 only. And the model's code now runs in THIS process, so the direct approach's hardened code
guard (``aw_agent.harden_guard``, a stricter ``SafetyGuard.is_syntax_safe``) is applied here, before
any world exists. It is benchmark-side infrastructure, the same for every candidate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                                  # a project: aw_agent.py is copied next to us
sys.path.insert(1, str(_HERE.parents[1] / "adapters"))          # the repo: the direct example's adapters/


def main(argv: list[str]) -> int:
    port, root = int(argv[1]), argv[2]
    os.environ["APPWORLD_ROOT"] = root
    import aw_agent as core  # noqa: PLC0415  (the direct approach's harness, copied into the project)
    core.harden_guard()
    import uvicorn  # noqa: PLC0415
    from appworld.serve.environment import app  # noqa: PLC0415
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
