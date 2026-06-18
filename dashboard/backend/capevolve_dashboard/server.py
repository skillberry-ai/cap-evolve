"""Idempotent launcher for the dashboard server + CLI entrypoint."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path


def url_for(port: int, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{port}"


def is_up(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with urllib.request.urlopen(f"{url_for(port, host)}/api/health", timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False


def resolve_static_dir() -> Path | None:
    # server.py(file) -> capevolve_dashboard[0] -> backend[1] -> dashboard[2];
    # the built SPA lives at dashboard/frontend/dist.
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return dist if dist.is_dir() else None


def ensure_up(base_dir, port: int = 7878, open_browser: bool = True) -> str:
    url = url_for(port)
    if is_up(port):
        if open_browser:
            webbrowser.open(url)
        return url
    env = dict(os.environ, CAPEVOLVE_BASE_DIR=str(base_dir))
    static = resolve_static_dir()
    if static:
        env["CAPEVOLVE_STATIC_DIR"] = str(static)
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "capevolve_dashboard.asgi:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if open_browser:
        webbrowser.open(url)
    return url


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cap-evolve-dashboard")
    p.add_argument("--base", default=".capevolve")
    p.add_argument("--port", type=int, default=7878)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args(argv)
    url = ensure_up(args.base, port=args.port, open_browser=not args.no_open)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
