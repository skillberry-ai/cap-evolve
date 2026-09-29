#!/usr/bin/env python
"""Start tau2's Environment Manager — the benchmark's environment service, over HTTP.

The blackbox arm needs one: store-hosted tools execute in the STORE's process, not where the
benchmark's state lives, so a skill's tools can only reach that state through a service the
benchmark provides. The intervention health-checks this service and aborts without it.

`EnvironmentManager` is **upstream tau2**, not something this repo adds — only this launcher is
ours, which is why it lives here rather than in the (unmodified) benchmark checkout.

    python scripts/start_tau2_env_manager.py [--host 127.0.0.1] [--port 8004]

Two operational facts worth knowing:

* Startup takes ~10s because importing tau2 pulls in litellm. POLL the port rather than
  sleeping a fixed amount.
* Probe ``/docs`` or ``/`` — this FastAPI app serves NO ``/health``, so probing that reports a
  live service as dead and a readiness loop burns every attempt.

``LITELLM_LOCAL_MODEL_COST_MAP=True`` is set here rather than left to the caller: without it
litellm attempts a remote cost-map fetch that cannot succeed on a sealed runner and stalls
startup until it times out.
"""

from __future__ import annotations

import argparse
import asyncio
import os


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="start_tau2_env_manager")
    p.add_argument("--host", default=os.environ.get("TAU2_ENV_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("ENV_PORT", "8004")))
    args = p.parse_args(argv)

    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

    from tau2.orchestrator.environment_manager import EnvironmentManager

    print(f"tau2 environment service -> http://{args.host}:{args.port}  "
          f"(readiness: GET /docs or /, NOT /health)", flush=True)
    asyncio.run(EnvironmentManager(host=args.host, port=args.port).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
