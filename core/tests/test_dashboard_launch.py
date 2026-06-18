"""The pipeline's dashboard auto-launch wiring: mode resolution, command shape,
and the guarantee that launching never raises or blocks the run."""

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


def test_maybe_launch_spawns_when_available(monkeypatch):
    calls = {}
    monkeypatch.setattr(dl, "is_available", lambda: True)

    def fake_popen(cmd, **kw):
        calls["cmd"] = cmd
        return object()

    monkeypatch.setattr(dl.subprocess, "Popen", fake_popen)
    out = dl.maybe_launch("/runs", mode="auto", port=7878)
    assert out["dashboard"] == "http://127.0.0.1:7878"
    assert calls["cmd"][1:3] == ["-m", "capevolve_dashboard.server"]


def test_maybe_launch_never_raises_on_spawn_error(monkeypatch):
    monkeypatch.setattr(dl, "is_available", lambda: True)

    def boom(cmd, **kw):
        raise OSError("no exec")

    monkeypatch.setattr(dl.subprocess, "Popen", boom)
    out = dl.maybe_launch("/runs", mode="auto")
    assert out["dashboard"] == "error"
