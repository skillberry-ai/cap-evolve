#!/usr/bin/env python3
"""Launch evograph's weakness-graph view for a cap-evolve run and register it.

The evograph algorithm (agent mode) writes its wiki into the cap-evolve run dir
(`<run_dir>/wiki/...`, `<run_dir>/runs/...`). This script:

  1. writes `<run_dir>/custom_view.json` = {title, url} so the cap-evolve dashboard
     mounts a "Weakness graph" tab embedding this view (the #39 custom-view contract);
  2. serves evo-graph's read-only React dashboard (the bundled `dashboard/frontend/dist`)
     via its FastAPI backend, pointed at the run dir (`EVOGRAPH_BASE=<run_dir>`).

The backend is strictly read-only — it only reads the wiki/results/logs the agent
writes. Run it in the background:

    python scripts/view.py --run-dir <abs run_dir> --port 7878 &

Then the cap-evolve dashboard shows the embedded weakness graph, and the evograph
UI is also reachable directly at the printed URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
BACKEND = DASHBOARD / "backend"
DIST = DASHBOARD / "frontend" / "dist"


def write_custom_view(run_dir: Path, url: str, title: str = "Weakness graph") -> None:
    """Declare the view to the cap-evolve dashboard (#39 contract)."""
    (run_dir / "custom_view.json").write_text(
        json.dumps({"title": title, "url": url}), encoding="utf-8"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="evograph-view")
    p.add_argument("--run-dir", required=True, help="the cap-evolve run dir (holds wiki/ and runs/)")
    p.add_argument("--port", type=int, default=7878)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--register-only", action="store_true",
                   help="write custom_view.json and exit (do not start the server)")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        sys.stderr.write(f"run dir not found: {run_dir}\n")
        return 1

    url = f"http://{args.host}:{args.port}/"
    write_custom_view(run_dir, url)
    print(json.dumps({"custom_view": str(run_dir / "custom_view.json"), "url": url}))
    if args.register_only:
        return 0

    os.environ["EVOGRAPH_BASE"] = str(run_dir)
    os.environ["EVOGRAPH_DIST"] = str(DIST)
    sys.path.insert(0, str(BACKEND))
    try:
        import uvicorn
    except ImportError:
        sys.stderr.write(
            "evograph view needs fastapi + uvicorn:\n"
            f"  pip install -r {BACKEND / 'requirements.txt'}\n"
        )
        return 1
    uvicorn.run("app:app", host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
