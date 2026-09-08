"""``watchdog.py`` — notices a dead `host.py` process and relaunches it.

Pure logic: no real subprocess is ever spawned here. Every case injects a stub
`relaunch` callable and asserts what `check()` decided and what it would have run,
not that a process actually started.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WATCHDOG_PATH = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "watchdog.py"

_spec = importlib.util.spec_from_file_location("agent_optimize_watchdog", WATCHDOG_PATH)
watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watchdog)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _relaunch_spy():
    calls = []

    def _fn(cmd, log_path):
        calls.append({"cmd": cmd, "log_path": log_path})

    return _fn, calls


def test_a_run_with_no_heartbeat_yet_is_left_alone(tmp_path):
    out = watchdog.check(tmp_path)
    assert out["action"] == "none"
    assert "heartbeat" in out["reason"]


def test_a_sealed_run_is_never_touched_even_with_a_dead_heartbeat(tmp_path):
    (tmp_path / "final.json").write_text("{}", encoding="utf-8")
    _write(tmp_path / "host" / "heartbeat.json", {"pid": 999999, "ts": time.time() - 3600})
    out = watchdog.check(tmp_path)
    assert out["action"] == "none"
    assert "sealed" in out["reason"]


def test_a_live_pid_is_not_relaunched_regardless_of_heartbeat_age(tmp_path):
    _write(tmp_path / "host" / "heartbeat.json", {"pid": os.getpid(), "ts": time.time() - 3600})
    _write(tmp_path / "host" / "launch_args.json",
           {"python": sys.executable, "argv": ["--run-dir", str(tmp_path)]})
    fn, calls = _relaunch_spy()
    out = watchdog.check(tmp_path, relaunch=fn)
    assert out["action"] == "none"
    assert "alive" in out["reason"]
    assert calls == []


def test_a_recently_dead_pid_under_the_threshold_is_not_yet_relaunched(tmp_path):
    _write(tmp_path / "host" / "heartbeat.json", {"pid": 999999, "ts": time.time() - 30})
    fn, calls = _relaunch_spy()
    out = watchdog.check(tmp_path, stale_seconds=600, relaunch=fn)
    assert out["action"] == "none"
    assert "threshold" in out["reason"]
    assert calls == []


def test_a_stale_dead_heartbeat_with_no_launch_args_reports_an_error_not_a_guess(tmp_path):
    _write(tmp_path / "host" / "heartbeat.json", {"pid": 999999, "ts": time.time() - 3600})
    out = watchdog.check(tmp_path, stale_seconds=600)
    assert out["action"] == "error"
    assert "launch_args.json" in out["reason"]


def test_a_stale_dead_heartbeat_relaunches_with_the_saved_command_line(tmp_path):
    _write(tmp_path / "host" / "heartbeat.json", {"pid": 999999, "ts": time.time() - 3600})
    _write(tmp_path / "host" / "launch_args.json",
           {"python": "/usr/bin/python3.11",
            "argv": ["--run-dir", str(tmp_path), "--project", "/p", "--agent", "claude-code"]})
    fn, calls = _relaunch_spy()
    out = watchdog.check(tmp_path, stale_seconds=600, relaunch=fn)
    assert out["action"] == "relaunched"
    assert len(calls) == 1
    cmd = calls[0]["cmd"]
    assert cmd[0] == "/usr/bin/python3.11"
    assert cmd[1] == str(watchdog.HOST_PY)
    assert cmd[2:] == ["--run-dir", str(tmp_path), "--project", "/p",
                       "--agent", "claude-code"]
    assert calls[0]["log_path"] == tmp_path / "host_launch.log"


def test_dry_run_reports_would_relaunch_and_never_calls_relaunch(tmp_path):
    _write(tmp_path / "host" / "heartbeat.json", {"pid": 999999, "ts": time.time() - 3600})
    _write(tmp_path / "host" / "launch_args.json",
           {"python": sys.executable, "argv": ["--run-dir", str(tmp_path)]})
    fn, calls = _relaunch_spy()
    out = watchdog.check(tmp_path, stale_seconds=600, relaunch=fn, dry_run=True)
    assert out["action"] == "would_relaunch"
    assert calls == []


def test_a_missing_run_dir_is_an_error():
    out = watchdog.check(Path("/no/such/run/dir/xyz"))
    assert out["action"] == "error"


def test_cli_exit_code_is_nonzero_only_on_an_actual_error(tmp_path, capsys):
    rc = watchdog.main(["--run-dir", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["action"] == "none"

    rc = watchdog.main(["--run-dir", "/no/such/run/dir/xyz"])
    assert rc == 1
