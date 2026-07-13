#!/usr/bin/env python3
"""Entry point for the EvoGraph dashboard backend.

Launched by bootstrap.py with cwd = .evograph/ and EVOGRAPH_BASE / EVOGRAPH_DIST set in the env.
Can also be run directly:  python server.py --port 8765  (reads EVOGRAPH_BASE, default cwd).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EvoGraph dashboard backend.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--base", type=Path, default=None, help="The .evograph dir (default: $EVOGRAPH_BASE or cwd).")
    args = parser.parse_args()

    if args.base is not None:
        os.environ["EVOGRAPH_BASE"] = str(args.base.resolve())
    os.environ.setdefault("EVOGRAPH_BASE", str(Path.cwd()))

    # Make `import app` work regardless of where we're launched from.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    try:
        import uvicorn
    except ImportError:
        sys.stderr.write(
            "EvoGraph dashboard needs fastapi + uvicorn. Install with:\n"
            "  pip install -r " + str(Path(__file__).resolve().parent / "requirements.txt") + "\n"
        )
        return 1

    uvicorn.run("app:app", host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
