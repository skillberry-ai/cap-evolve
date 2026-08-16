"""The pipeline's dashboard auto-launch wiring: mode resolution, command shape,
and the guarantee that launching never raises or blocks the run."""

import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import dashboard_launch as dl  # noqa: E402


def test_resolve_mode_precedence():
    assert dl.resolve_mode("off", "auto") == "off"          # cli wins
    assert dl.resolve_mode(None, "report-only") == "report-only"  # spec next
    assert dl.resolve_mode(None, None) == "auto"             # default
    assert dl.resolve_mode("bogus", "nonsense") == "auto"    # unknown -> default


def test_launch_command_shape():
    cmd = dl.launch_command("/runs", port=7999, open_browser=False)
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "capevolve_dashboard.server"]
    assert "--base" in cmd and "/runs" in cmd
    assert "--port" in cmd and "7999" in cmd
    assert "--no-open" in cmd


def test_launch_command_opens_by_default():
    assert "--no-open" not in dl.launch_command("/runs")


def test_maybe_launch_off_is_noop():
    assert dl.maybe_launch("/runs", mode="off") == {"dashboard": "off"}


def test_maybe_launch_skips_when_unavailable(monkeypatch):
    # Simulate the optional package not being installed: no spawn, no raise.
    monkeypatch.setattr(dl, "is_available", lambda: False)
    out = dl.maybe_launch("/runs", mode="auto")
    assert out["dashboard"] == "skipped"
    assert "not installed" in out["reason"]


def _fake_spawn(monkeypatch, calls):
    monkeypatch.setattr(dl, "is_available", lambda: True)

    def fake_popen(cmd, **kw):
        calls["cmd"] = cmd
        return object()

    monkeypatch.setattr(dl.subprocess, "Popen", fake_popen)


def test_maybe_launch_spawns_when_available(monkeypatch):
    calls = {}
    _fake_spawn(monkeypatch, calls)
    # Pick a port that is genuinely free right now instead of hard-coding one:
    # a stray dashboard (or any unrelated server) on a fixed port must not fail us.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
    out = dl.maybe_launch("/runs", mode="auto", port=free)
    assert out["dashboard"] == f"http://127.0.0.1:{free}"
    assert calls["cmd"][1:3] == ["-m", "capevolve_dashboard.server"]
    assert str(free) in calls["cmd"]


def test_maybe_launch_steps_past_an_occupied_port(monkeypatch):
    """A server already squatting the requested port must not be reused: the
    stale server would keep serving a DIFFERENT run's base directory."""
    calls = {}
    _fake_spawn(monkeypatch, calls)
    with socket.socket() as squatter:
        squatter.bind(("127.0.0.1", 0))
        squatter.listen(1)
        taken = squatter.getsockname()[1]
        out = dl.maybe_launch("/runs", mode="auto", port=taken)
    assert out["dashboard"] != f"http://127.0.0.1:{taken}"
    assert str(taken) not in calls["cmd"]


def test_maybe_launch_never_raises_on_spawn_error(monkeypatch):
    monkeypatch.setattr(dl, "is_available", lambda: True)

    def boom(cmd, **kw):
        raise OSError("no exec")

    monkeypatch.setattr(dl.subprocess, "Popen", boom)
    out = dl.maybe_launch("/runs", mode="auto")
    assert out["dashboard"] == "error"


def test_report_records_a_given_url_instead_of_launching_a_second_server(tmp_path):
    """``cap-evolve run`` starts the dashboard, then the report phase used to call
    maybe_launch() again — and because _free_port() steps past an occupied port, that
    second call spawned a SECOND server on a SECOND port and reported that one. Every
    run leaked a process and printed two contradicting URLs.

    ``--dashboard-url`` is the fix: record what the caller already started, launch nothing.
    """
    import json
    import os
    import socket
    import subprocess

    report = REPO / "skills" / "phases" / "report" / "scripts" / "run.py"
    run_dir = tmp_path / "run_x"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "state.json").write_text(json.dumps({"best_id": "seed"}), encoding="utf-8")

    with socket.socket() as s:          # a port nothing is on, and must stay that way
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]

    env = dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE))
    proc = subprocess.run(
        [sys.executable, str(report), "--run-dir", str(run_dir), "--no-dashboard",
         "--dashboard-mode", "auto", "--dashboard-port", str(free),
         "--dashboard-url", "http://127.0.0.1:9/already-up"],
        capture_output=True, text=True, env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert json.loads(proc.stdout)["dashboard_server"] == "http://127.0.0.1:9/already-up"

    # nothing was spawned on the port we offered
    with socket.socket() as probe:
        probe.settimeout(0.5)
        assert probe.connect_ex(("127.0.0.1", free)) != 0, "a second server was launched"
