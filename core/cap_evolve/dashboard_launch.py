"""Best-effort launcher that wires the (optional) live dashboard into the pipeline.

The stdlib-only core never imports the dashboard's web stack. Instead it spawns
the optional ``capevolve-dashboard`` package as a detached subprocess
(``python -m capevolve_dashboard.server``), which is idempotent (it reuses an
already-running server on the port). If that package isn't installed, launching
is a no-op with a friendly hint — the run is never affected.
"""
from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
from pathlib import Path

MODES = ("auto", "report-only", "off")
DEFAULT_PORT = 7878


def _free_port(start: int, tries: int = 25) -> int:
    """First free TCP port at/above ``start`` so we never reuse a stale server.

    The dashboard server binds a port and serves whatever ``--base`` it was given;
    if another (possibly unrelated) server already holds ``start``, our spawn would
    silently fail to bind and that stale server would keep serving the WRONG run.
    Picking a free port guarantees this run gets its own dashboard on its own base.
    """
    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def resolve_mode(cli_arg: str | None, spec_value: str | None, default: str = "auto") -> str:
    """Precedence: explicit CLI flag > spec field > default. Unknown → default."""
    for candidate in (cli_arg, spec_value, default):
        if candidate in MODES:
            return candidate
    return default


def is_available() -> bool:
    """True if the optional dashboard package is importable in this interpreter."""
    return importlib.util.find_spec("capevolve_dashboard") is not None


def launch_command(base_dir, port: int = DEFAULT_PORT, open_browser: bool = True) -> list[str]:
    """The argv that (idempotently) ensures the dashboard server is up."""
    cmd = [sys.executable, "-m", "capevolve_dashboard.server",
           "--base", str(base_dir), "--port", str(port)]
    if not open_browser:
        cmd.append("--no-open")
    return cmd


def url_for(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def maybe_launch(base_dir, *, mode: str, port: int = DEFAULT_PORT,
                 open_browser: bool = True) -> dict:
    """Spawn the dashboard server unless mode is ``off``. Never raises.

    Returns a small status dict (``{"dashboard": url}`` or ``{"dashboard":
    "skipped", "reason": ...}``) suitable for printing as part of a phase summary.
    """
    if mode == "off":
        return {"dashboard": "off"}
    if not is_available():
        return {"dashboard": "skipped",
                "reason": "capevolve-dashboard not installed "
                          "(pip install -e dashboard/backend)"}
    port = _free_port(port)  # avoid reusing a stale server squatting the default port
    try:
        subprocess.Popen(
            launch_command(Path(base_dir), port=port, open_browser=open_browser),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:  # noqa: BLE001 — launching must never break the run
        return {"dashboard": "error", "reason": str(e)}
    return {"dashboard": url_for(port)}
