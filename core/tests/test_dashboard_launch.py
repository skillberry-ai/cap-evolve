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


def test_maybe_launch_reports_error_when_every_port_in_range_is_taken(monkeypatch):
    """Every port in the scanned range squatted (observed live: ~25 leaked
    dashboard processes from old sessions) must surface as an error, not silently
    fall back to the first (also-taken) port — that fallback used to print a URL
    that actually served a stale, unrelated dashboard."""
    monkeypatch.setattr(dl, "is_available", lambda: True)
    monkeypatch.setattr(dl, "pick_port", lambda base, start, tries=25: (_ for _ in ()).throw(
        RuntimeError(f"no free port in [{start}, {start + tries})")))
    out = dl.maybe_launch("/runs", mode="auto")
    assert out["dashboard"] == "error"
    assert "no free port" in out["reason"]


# --- #628: reuse / skip-live / reap-orphan port selection -------------------------
# A real subprocess plays a dashboard server: it answers /api/health with whatever
# card we give it plus its own pid, exactly like capevolve_dashboard.app does.
_FAKE_DASH = r"""
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
card = json.loads(sys.argv[1])
if card.pop("with_pid", True):
    card["pid"] = os.getpid()
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(card).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 0), H)
print(srv.server_address[1], flush=True)
srv.serve_forever()
"""


def _fake_dashboard(card: dict):
    import json
    import subprocess
    proc = subprocess.Popen([sys.executable, "-c", _FAKE_DASH, json.dumps(card)],
                            stdout=subprocess.PIPE, text=True)
    return proc, int(proc.stdout.readline())


def _card(base, **kw):
    return {"ok": True, "app": "cap-evolve-dashboard", "base_dir": str(base), **kw}


def test_live_dashboard_for_another_base_is_skipped_never_reaped(tmp_path):
    """Another session's dashboard (its base exists) is ambiguous -> left alone; with
    nothing else in range we report an error rather than kill it."""
    other = tmp_path / "other_session"
    other.mkdir()
    proc, port = _fake_dashboard(_card(other, code="X"))
    try:
        try:
            dl.pick_port(tmp_path / "mine", port, tries=1)
            raise AssertionError("should have raised")
        except RuntimeError as e:
            assert "none provably orphaned" in str(e)
        assert proc.poll() is None, "a live session's dashboard was killed"
    finally:
        proc.kill()


def test_live_dashboard_for_same_base_and_code_is_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "code_stamp", lambda: "X")
    proc, port = _fake_dashboard(_card(tmp_path.resolve(), code="X"))
    try:
        assert dl.pick_port(tmp_path, port, tries=1) == (port, True)
        assert proc.poll() is None
    finally:
        proc.kill()


def test_same_base_but_stale_code_is_not_reused_or_killed(tmp_path, monkeypatch):
    """Old backend code under a fresh frontend is the #575 "broken dashboard" illusion:
    never attach to it; it still serves a live base, so never kill it either."""
    monkeypatch.setattr(dl, "code_stamp", lambda: "NEW")
    proc, port = _fake_dashboard(_card(tmp_path.resolve(), code="OLD"))
    try:
        try:
            dl.pick_port(tmp_path, port, tries=1)
            raise AssertionError("should have raised")
        except RuntimeError:
            pass
        assert proc.poll() is None
    finally:
        proc.kill()


def test_orphan_whose_base_dir_is_gone_is_reaped(tmp_path):
    gone = tmp_path / "deleted_base"           # never created: nothing can be served
    proc, port = _fake_dashboard(_card(gone))
    try:
        assert dl.pick_port(tmp_path, port, tries=1) == (port, False)
        assert proc.wait(timeout=5) is not None, "orphan was not reaped"
    finally:
        proc.kill()


def test_reapable_is_conservative(tmp_path):
    gone = str(tmp_path / "gone")
    assert dl._reapable({"pid": 4242, "base_dir": gone})
    assert not dl._reapable({"base_dir": gone})                    # old server: no pid
    assert not dl._reapable({"pid": 1, "base_dir": gone})          # never init
    assert not dl._reapable({"pid": 4242, "base_dir": str(tmp_path)})  # base exists
    assert not dl._reapable({"pid": 4242, "base_dir": "rel/gone"})  # relative: cwd unknown


def test_unidentified_listener_is_never_reaped(tmp_path):
    """No pid in the card (pre-#628 servers) -> unprovable -> left running."""
    proc, port = _fake_dashboard(_card(tmp_path / "gone", with_pid=False))
    try:
        try:
            dl.pick_port(tmp_path, port, tries=1)
            raise AssertionError("should have raised")
        except RuntimeError:
            pass
        assert proc.poll() is None
    finally:
        proc.kill()


def test_banner_names_url_and_base(tmp_path):
    b = dl.banner({"dashboard": "http://127.0.0.1:7999", "base_dir": str(tmp_path),
                   "reused": True})
    assert "http://127.0.0.1:7999" in b and str(tmp_path) in b and "reusing" in b
    assert "NOT running" in dl.banner({"dashboard": "error", "reason": "no free port"})


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
