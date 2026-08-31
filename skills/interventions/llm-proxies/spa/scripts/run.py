#!/usr/bin/env python3
"""Report the state of the SPA intervention stack. Read-only.

This is the skill's registry ``entry`` (see meta.yaml) and deliberately does nothing
else: the intervention is a LIBRARY. Provisioning, starting, deploying and cleaning are
``spa_env`` calls, made by the adapter that needs them or by an example's own
setup/teardown script — not by a command layer wrapping them.

    python skills/interventions/llm-proxies/spa/scripts/run.py [--json]

Exit code 0 when store and SPA are both healthy, 1 otherwise, so a shell caller can
gate on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spa_env  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="spa-status", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    st = spa_env.status()
    if args.json:
        print(json.dumps(st, indent=2))
    else:
        for name in ("store", "spa"):
            r = st[name]
            # A port held by someone who is not our service is the failure mode worth
            # shouting about: it looks identical to "down" but needs a different fix.
            foreign = f"  (port held by {r['pids']} — NOT ours)" if r["pids"] and not r["ours"] else ""
            provisioned = "" if r["provisioned"] else "  [not provisioned]"
            print(f"  {name:<6} {'healthy' if r['healthy'] else 'down':<8} "
                  f"port {r['port']}{provisioned}{foreign}")
        env = st["remote_env"]
        state = "healthy" if env["healthy"] else ("down" if env["url"] else "not configured")
        print(f"  {'remote':<6} {state:<8} {env['url'] or '(set SPA_REMOTE_ENV_URL)'}")
    return 0 if (st["store"]["healthy"] and st["spa"]["healthy"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
