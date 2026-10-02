"""Best-effort launcher that wires the (optional) live dashboard into the pipeline.

The stdlib-only core never imports the dashboard's web stack. Instead it spawns
the optional ``capevolve-dashboard`` package as a detached subprocess
(``python -m capevolve_dashboard.server``), which is idempotent (it reuses an
already-running server on the port). If that package isn't installed, launching
is a no-op with a friendly hint — the run is never affected.
"""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODES = ("auto", "report-only", "off")
DEFAULT_PORT = 7878
PORT_RANGE = 100  # was 25: leaked servers exhausted it on a shared machine (#628)


def _is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # SO_REUSEADDR like uvicorn: a port whose only remnants are TIME_WAIT sockets
        # (e.g. left by our own health probe of a just-reaped server) IS usable. It
        # never permits binding over a live LISTEN socket.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _probe(port: int) -> dict | None:
    """The ``/api/health`` card of a cap-evolve dashboard on ``port``, else None."""
    try:
        with urllib.request.urlopen(f"{url_for(port)}/api/health", timeout=0.5) as r:
            h = json.load(r)
    except Exception:  # noqa: BLE001 — not HTTP / not up / garbage: all mean "unknown"
        return None
    return h if isinstance(h, dict) and h.get("app") == "cap-evolve-dashboard" else None


def code_stamp() -> str | None:
    """Identity of the installed dashboard code; must match the server's health ``code``
    (see capevolve_dashboard/app.py): package dir @ newest ``*.py`` mtime."""
    spec = importlib.util.find_spec("capevolve_dashboard")
    if not spec or not spec.submodule_search_locations:
        return None
    pkg = Path(next(iter(spec.submodule_search_locations))).resolve()
    return f"{pkg}@{max(f.stat().st_mtime_ns for f in pkg.glob('*.py'))}"


def _reapable(h: dict) -> bool:
    """True only for a listener that is PROVABLY ours and PROVABLY dead weight.

    ``h`` already passed ``_probe`` (it answered our health endpoint as
    ``cap-evolve-dashboard``). It must also self-report its pid AND serve an absolute
    base dir that no longer exists — so it can show nobody anything. A live base, an
    older server that reports no pid, or a foreign process is ambiguous: never killed.
    """
    pid, base = h.get("pid"), h.get("base_dir")
    return (isinstance(pid, int) and pid > 1 and isinstance(base, str)
            and os.path.isabs(base) and not os.path.exists(base))


def pick_port(base_dir, start: int, tries: int = PORT_RANGE) -> tuple[int, bool]:
    """``(port, reused)`` for this base's dashboard, scanning ``[start, start + tries)``.

    1. REUSE a listener already serving this exact base with this exact dashboard code.
       Spawning a fresh server every run is what leaked one process per run until the
       range was exhausted (#628). A different base or different code is NOT reused —
       it would serve the wrong run, or a stale API under a fresh frontend.
    2. Else the first free port.
    3. Else reap listeners ``_reapable`` proves dead; take the first one that frees.
    4. Else raise — never fall back to a taken port (that printed a URL serving a
       stale, unrelated dashboard). Callers decide how to surface it.
    """
    base, stamp = str(Path(base_dir).resolve()), code_stamp()
    free, dead = None, []
    for p in range(start, start + tries):
        if _is_free(p):
            free = p if free is None else free
            continue
        h = _probe(p)
        if h is None:
            continue
        if stamp and h.get("base_dir") == base and h.get("code") == stamp:
            return p, True
        if _reapable(h):
            dead.append((p, h["pid"]))
    if free is not None:
        return free, False
    for p, pid in dead:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue
        for _ in range(30):
            if _is_free(p):
                return p, False
            time.sleep(0.1)
    raise RuntimeError(
        f"no free port in [{start}, {start + tries}) — {tries} candidates all taken, none "
        "provably orphaned; leaked dashboard servers from prior runs may be squatting this "
        "range (inspect: lsof -nP -iTCP -sTCP:LISTEN; stop them all if none are in use: "
        "pkill -f capevolve_dashboard.asgi)")


def banner(status: dict) -> str:
    """A hard-to-miss block naming the URL and the base dir that server is serving."""
    url = status.get("dashboard")
    if not (isinstance(url, str) and url.startswith("http")):
        return f"!!! cap-evolve dashboard NOT running: {status.get('reason', url)}"
    how = "reusing existing server" if status.get("reused") else "started"
    bar = "=" * 72
    return f"{bar}\n  DASHBOARD  {url}   ({how})\n  serving    {status.get('base_dir')}\n{bar}"


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
    try:
        port, reused = pick_port(base_dir, port)
    except Exception as e:  # noqa: BLE001 — launching must never break the run
        return {"dashboard": "error", "reason": str(e)}
    try:
        # Spawned on reuse too: the server CLI is idempotent (port already up -> it
        # just opens the browser and exits), so no second server is started.
        subprocess.Popen(
            launch_command(Path(base_dir), port=port, open_browser=open_browser),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:  # noqa: BLE001 — launching must never break the run
        return {"dashboard": "error", "reason": str(e)}
    return {"dashboard": url_for(port), "base_dir": str(Path(base_dir).resolve()),
            "reused": reused}
