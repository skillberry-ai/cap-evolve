"""watchdog.py — notice when ``host.py`` itself died, and relaunch it.

``host.py``'s own docstring covers every way the AGENT it launches can stop short —
turn budget, a backgrounded wait, a transient CLI crash — because in each of those cases
host.py is still alive to diagnose and (for a transient crash) retry. None of that helps
when host.py's OS process dies: the machine sleeps, the terminal running it closes, the
CI runner is preempted. The process just stops, mid tool-call, with no exit code anyone
sees and no ``final.json``. Re-running host.py against the same run dir is already safe
(``commit.py`` refuses to double-book a decided candidate; ``_seal`` is idempotent) — this
script only automates *noticing* that it needs to happen and doing it, so a run does not
sit silently stalled until a human happens to look.

Run it periodically (cron, a loop, CI) alongside host.py, once per run dir being watched.
It does ONE check per invocation and exits — no internal sleep loop, no daemon.

What it is not: a way to resume a hung turn inside the agent's own conversation. host.py's
briefing already states that invariant (delegate the work, never the waiting) because
ending a turn with work outstanding ends the process with nothing left to resume from
the inside. This script only restarts the OUTER process from the outside, which then
starts a fresh turn against the same run dir.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST_PY = HERE / "host.py"

#: Heartbeat age past which host.py is presumed dead if its pid is also gone. Several
#: multiples of `host.py`'s HEARTBEAT_INTERVAL_SECONDS (60s), so one missed write from a
#: slow disk or a GC pause never reads as a crash.
DEFAULT_STALE_SECONDS = 10 * 60


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just owned by someone else — still alive
    except OSError:
        return False
    return True


def _default_relaunch(cmd: list[str], log_path: Path) -> None:
    """Detached, output redirected to `log_path` — the file this run's launch was missing,
    which is what made the original stall so hard to see after the fact.
    """
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def check(run_dir: Path, *, stale_seconds: int = DEFAULT_STALE_SECONDS,
          host_py: Path = HOST_PY, relaunch=_default_relaunch, dry_run: bool = False) -> dict:
    """One staleness check + (maybe) relaunch. Returns a JSON-serializable report.

    ``relaunch`` is a seam for tests: a callable ``(cmd, log_path) -> None``, never invoked
    for real when ``dry_run`` is set.
    """
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        return {"run_dir": str(run_dir), "action": "error", "reason": "run dir not found"}

    if (run_dir / "final.json").exists():
        return {"run_dir": str(run_dir), "action": "none",
                 "reason": "already sealed (final.json present)"}

    heartbeat = _read_json(run_dir / "host" / "heartbeat.json")
    if heartbeat is None:
        return {"run_dir": str(run_dir), "action": "none",
                 "reason": "no host/heartbeat.json — host.py has not started an agent "
                           "invocation yet, or this run predates the heartbeat"}

    age = time.time() - float(heartbeat.get("ts") or 0.0)
    pid = heartbeat.get("pid")
    if _pid_alive(pid):
        return {"run_dir": str(run_dir), "action": "none",
                 "reason": f"pid {pid} is alive", "age_seconds": round(age, 1)}

    if age < stale_seconds:
        return {"run_dir": str(run_dir), "action": "none",
                 "reason": f"heartbeat is {age:.0f}s old, under the {stale_seconds}s "
                           "threshold — pid is gone but may just be between attempts",
                 "age_seconds": round(age, 1)}

    launch = _read_json(run_dir / "host" / "launch_args.json")
    if launch is None:
        return {"run_dir": str(run_dir), "action": "error",
                 "reason": "heartbeat is stale and its pid is gone, but "
                           "host/launch_args.json is missing — cannot reconstruct the "
                           "original command line to relaunch it",
                 "age_seconds": round(age, 1)}

    cmd = [str(launch.get("python") or sys.executable), str(host_py),
           *[str(a) for a in (launch.get("argv") or [])]]
    log_path = run_dir / "host_launch.log"
    report = {"run_dir": str(run_dir), "cmd": cmd, "age_seconds": round(age, 1),
              "log": str(log_path)}
    if dry_run:
        report["action"] = "would_relaunch"
        return report
    relaunch(cmd, log_path)
    report["action"] = "relaunched"
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="watchdog.py",
        description="Check a cap-evolve run dir's host.py heartbeat; relaunch it if stale.")
    p.add_argument("--run-dir", required=True, help="run dir host.py was launched against")
    p.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_SECONDS / 60,
                   help=f"heartbeat age, in minutes, before host.py is presumed dead "
                        f"(default {DEFAULT_STALE_SECONDS / 60:g})")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would happen without actually relaunching")
    args = p.parse_args(argv)

    out = check(Path(args.run_dir), stale_seconds=args.stale_minutes * 60, dry_run=args.dry_run)
    print(json.dumps(out, indent=2))
    return 1 if out["action"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
