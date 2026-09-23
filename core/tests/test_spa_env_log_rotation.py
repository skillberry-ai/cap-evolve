"""Log rotation and log placement for the SPA intervention skill.

Every log this stack produces must live in /tmp and be bounded. On main, spa_env additionally
captured make's stdout into vendor/<repo>/{store.log,proxy-agent.log} with open("ab") — append,
never truncated, never rotated; proxy-agent.log was measured past 100MB, and 14.4MB inside a single
10-minute run.

These tests drive the REAL rotate_if_large and the REAL _start_detached rather than grepping the
source, because the defects this code is prone to are a mis-ordered generation shuffle and a
mis-placed call (rotating a log a live process holds open), neither of which a source check sees.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SPA_ENV = (Path(__file__).resolve().parents[2]
           / "skills/interventions/llm-proxies/spa/scripts/spa_env.py")


@pytest.fixture(scope="module")
def spa_env():
    """The skill is not an installed package, so load it by path."""
    spec = importlib.util.spec_from_file_location("spa_env_under_test", SPA_ENV)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def isolate_log_knobs(spa_env, monkeypatch):
    """Keep these tests independent of the developer's repo-root .env.

    rotate_if_large now reads the knobs through load_env(), which imports .env into os.environ --
    correct behaviour, but it means a ceiling set in a real .env silently overrides a monkeypatched
    LOG_MAX_BYTES and the assertions here become environment-dependent.
    """
    monkeypatch.delenv("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES", raising=False)
    monkeypatch.delenv("CAPEVOLVE_SKILLBERRY_LOG_BACKUPS", raising=False)
    monkeypatch.setattr(spa_env, "load_env", lambda: None)


# ---------------------------------------------------------------------------
# rotate_if_large
# ---------------------------------------------------------------------------

def test_a_file_at_the_ceiling_is_left_alone(spa_env, tmp_path):
    log = tmp_path / "skillberry-agent.log"
    log.write_bytes(b"x" * 1024)
    spa_env.rotate_if_large(log, max_bytes=1024)
    assert log.read_bytes() == b"x" * 1024
    assert not (tmp_path / "skillberry-agent.log.1").exists(), "at the ceiling is not over it"


def test_a_file_over_the_ceiling_becomes_generation_one(spa_env, tmp_path):
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"y" * 2048)
    spa_env.rotate_if_large(log, max_bytes=1024)
    assert not log.exists(), "the live path must be free for the truncating >& redirect"
    assert (tmp_path / "skillberry-store.log.1").read_bytes() == b"y" * 2048


def test_a_missing_file_is_a_no_op(spa_env, tmp_path):
    spa_env.rotate_if_large(tmp_path / "absent.log", max_bytes=1)   # must not raise


def test_generations_shift_without_overwriting_each_other(spa_env, tmp_path):
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"new" * 1024)
    (tmp_path / "skillberry-store.log.1").write_bytes(b"gen1")
    (tmp_path / "skillberry-store.log.2").write_bytes(b"gen2")

    spa_env.rotate_if_large(log, max_bytes=1024, backups=3)

    assert (tmp_path / "skillberry-store.log.1").read_bytes() == b"new" * 1024
    assert (tmp_path / "skillberry-store.log.2").read_bytes() == b"gen1"
    assert (tmp_path / "skillberry-store.log.3").read_bytes() == b"gen2"
    assert sorted(q.name for q in tmp_path.iterdir()) == [
        "skillberry-store.log.1", "skillberry-store.log.2", "skillberry-store.log.3"]


def test_twelve_rotations_still_leave_exactly_three_backups(spa_env, tmp_path):
    """The generation shuffle is where an off-by-one hides: drive it well past `backups`."""
    log = tmp_path / "skillberry-store.log"
    for gen in range(12):
        log.write_bytes(f"run{gen}".encode() + b"z" * 2048)
        spa_env.rotate_if_large(log, max_bytes=1024, backups=3)

    survivors = sorted(q.name for q in tmp_path.iterdir())
    assert survivors == ["skillberry-store.log.1", "skillberry-store.log.2",
                         "skillberry-store.log.3"], "backups=3 must never grow a 4th generation"
    # newest first: .1 is the most recent rotation, .3 the oldest kept
    assert (tmp_path / "skillberry-store.log.1").read_bytes().startswith(b"run11")
    assert (tmp_path / "skillberry-store.log.2").read_bytes().startswith(b"run10")
    assert (tmp_path / "skillberry-store.log.3").read_bytes().startswith(b"run9")


def test_an_oserror_degrades_instead_of_blocking_a_start(spa_env, tmp_path):
    """A full disk or read-only mount is a reason to run degraded, never a reason to refuse to
    start a service. Simulated with a read-only parent, which makes rename(2) fail with EACCES.

    (Note a directory sitting at log.1 does NOT fail: directories rename fine, so it is simply
    shuffled along the generation chain. That was worth discovering — it is not an error path.)
    """
    d = tmp_path / "logs"
    d.mkdir()
    log = d / "skillberry-store.log"
    log.write_bytes(b"q" * 2048)
    d.chmod(0o500)                                     # readable + executable, NOT writable
    try:
        spa_env.rotate_if_large(log, max_bytes=1024)   # must not raise
        assert log.exists(), "the log is left in place when it cannot be rotated"
        assert not (d / "skillberry-store.log.1").exists()
    finally:
        d.chmod(0o700)                                 # so pytest can clean up


def test_the_ceiling_and_backup_count_come_from_the_environment(spa_env, tmp_path, monkeypatch):
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 512)
    monkeypatch.setattr(spa_env, "LOG_BACKUPS", 1)
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"a" * 1024)
    (tmp_path / "skillberry-store.log.1").write_bytes(b"old")

    spa_env.rotate_if_large(log)

    assert (tmp_path / "skillberry-store.log.1").read_bytes() == b"a" * 1024
    assert not (tmp_path / "skillberry-store.log.2").exists(), "backups=1 keeps one generation"


def test_a_value_set_only_in_dot_env_reaches_rotation(spa_env, tmp_path, monkeypatch):
    """The knobs must be read AFTER load_env(), not at import.

    load_env() imports the repo-root .env into os.environ, but it only runs inside provision() /
    start_store() / start_spa() — after this module's top level has finished. Reading os.environ at
    import time meant a value set only in .env silently never reached rotation, while the PR claimed
    it would. Regression test for that: no shell export, value only in the file.
    """
    monkeypatch.delenv("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES", raising=False)
    monkeypatch.delenv("CAPEVOLVE_SKILLBERRY_LOG_BACKUPS", raising=False)
    monkeypatch.setattr(spa_env, "_ENV_LOADED", False)          # let load_env() run again
    # Goes through monkeypatch, not os.environ directly: a raw mutation here leaked the variable
    # into later tests and silently overrode their ceilings.
    monkeypatch.setattr(spa_env, "load_env",
                        lambda: monkeypatch.setenv("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES", "1024"))

    logfile = tmp_path / "skillberry-store.log"
    logfile.write_bytes(b"z" * 2048)                            # over 1024, under the 5MB default

    spa_env.rotate_if_large(logfile)                            # no explicit max_bytes

    assert (tmp_path / "skillberry-store.log.1").exists(), (
        "a ceiling set only in .env must be honoured; reading it at import time misses it")


def test_a_shell_export_still_wins_over_the_file(spa_env, tmp_path, monkeypatch):
    """load_env() uses setdefault, so an exported value must not be overwritten by the file."""
    monkeypatch.setenv("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES", "1024")
    monkeypatch.setattr(spa_env, "_ENV_LOADED", False)
    # load_env() uses setdefault, so the file must not clobber what the shell already set.
    monkeypatch.setattr(spa_env, "load_env",
                        lambda: os.environ.setdefault("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES",
                                                      "999999999"))

    logfile = tmp_path / "skillberry-store.log"
    logfile.write_bytes(b"z" * 2048)
    spa_env.rotate_if_large(logfile)

    assert (tmp_path / "skillberry-store.log.1").exists(), "the exported 1024 must win, not the file"


# ---------------------------------------------------------------------------
# _start_detached wiring
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_popen(spa_env, monkeypatch):
    """Capture the shell command and handles instead of launching anything."""
    seen = {}

    def fake(argv, **kw):
        seen["cmd"] = argv[-1]
        seen["stdout"] = kw.get("stdout")
        seen["stderr"] = kw.get("stderr")
        seen["stdout_name"] = getattr(kw.get("stdout"), "name", None)
        seen["mode"] = getattr(kw.get("stdout"), "mode", None)
        return type("P", (), {"pid": 4242})()

    monkeypatch.setattr(spa_env.subprocess, "Popen", fake)
    return seen


def test_rotation_happens_before_the_process_is_launched(spa_env, fake_popen, tmp_path,
                                                         monkeypatch):
    """Ordering IS the contract: start-service.sh truncates the log, so rotating afterwards
    would rotate an empty file and lose the previous run."""
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"previous run" + b"." * 2048)
    rotated_at_launch = {}

    real = spa_env.subprocess.Popen

    def check(argv, **kw):
        rotated_at_launch["gen1"] = (tmp_path / "skillberry-store.log.1").exists()
        return real(argv, **kw)

    monkeypatch.setattr(spa_env.subprocess, "Popen", check)
    spa_env._start_detached(tmp_path, {}, log)

    assert rotated_at_launch["gen1"], "the log must already be rotated when make run starts"


def test_the_service_log_is_pinned_on_the_make_command_line(spa_env, fake_popen, tmp_path):
    """A command-line assignment is required: make lets makefile assignments beat the
    environment unless -e is given, but a command-line one outranks the makefile's `=`."""
    log = tmp_path / "skillberry-store.log"
    spa_env._start_detached(tmp_path, {}, log)
    assert f"make run SERVICE_LOG={log}" in fake_popen["cmd"], fake_popen["cmd"]


def test_the_pid_sentinel_is_never_overridden(spa_env, fake_popen, tmp_path):
    """SPA_PID_FILE / STORE_PID_FILE hardcode the default paths and stop/liveness read them."""
    spa_env._start_detached(tmp_path, {}, tmp_path / "skillberry-store.log")
    assert "SERVICE_SENTINEL" not in fake_popen["cmd"]


def test_no_log_is_written_outside_the_directory_we_were_given(spa_env, fake_popen, tmp_path):
    """Regression test for the deleted vendor/ capture: the service dir must stay log-free."""
    service_dir = tmp_path / "vendor" / "skillberry-store"
    service_dir.mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()

    spa_env._start_detached(service_dir, {}, logs / "skillberry-store.log")

    assert list(service_dir.rglob("*.log")) == [], "no log may land in the service's own directory"


# ---------------------------------------------------------------------------
# The two agent logs: ours is rotated, the agent's own is left alone
# ---------------------------------------------------------------------------

@pytest.fixture
def agent_ready(spa_env, monkeypatch, tmp_path):
    """Everything start_spa checks before it launches, stubbed to 'fine'."""
    d = tmp_path / "agent"
    (d / ".git").mkdir(parents=True)
    monkeypatch.setattr(spa_env, "agent_dir", lambda: d)
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "health_ok", lambda port, **kw: port != spa_env.SPA_PORT)
    monkeypatch.setattr(spa_env, "port_owner_conflict", lambda *a, **kw: None)
    monkeypatch.setattr(spa_env, "wait_for_health", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "SPA_PID_FILE", str(tmp_path / "agent.pid"))
    monkeypatch.setattr(spa_env, "AGENT_LOG_FILE", str(tmp_path / "skillberry-agent.log"))
    monkeypatch.setattr(spa_env, "AGENT_TOOLS_LOG_FILE", str(tmp_path / "tools-agent.log"))
    return d


def test_the_agent_service_log_is_pinned_and_rotated(spa_env, agent_ready, fake_popen, tmp_path,
                                                     monkeypatch):
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    log = tmp_path / "skillberry-agent.log"
    log.write_bytes(b"p" * 2048)

    spa_env.start_spa("my_skill")

    assert f"SERVICE_LOG={log}" in fake_popen["cmd"]
    assert (tmp_path / "skillberry-agent.log.1").read_bytes() == b"p" * 2048


def test_the_agents_own_log_path_is_pinned_in_the_environment(spa_env, agent_ready, fake_popen,
                                                              tmp_path):
    """We now DEPEND on tools-agent.log, so a future default change upstream must not move it."""
    captured = {}
    monkeypatch_target = spa_env.subprocess.Popen

    def grab(argv, **kw):
        captured["env"] = kw.get("env")
        return monkeypatch_target(argv, **kw)

    spa_env.subprocess.Popen = grab
    try:
        spa_env.start_spa("my_skill")
    finally:
        spa_env.subprocess.Popen = monkeypatch_target
    assert captured["env"]["SPA_ADVANCED__LOG_FILE"] == str(tmp_path / "tools-agent.log")


def test_an_explicit_caller_override_of_the_agent_log_still_wins(spa_env, agent_ready, tmp_path):
    captured = {}
    real = spa_env.subprocess.Popen

    def grab(argv, **kw):
        captured["env"] = kw.get("env")
        return type("P", (), {"pid": 1})()

    spa_env.subprocess.Popen = grab
    try:
        spa_env.start_spa("my_skill", SPA_ADVANCED__LOG_FILE="/tmp/elsewhere.log")
    finally:
        spa_env.subprocess.Popen = real
    assert captured["env"]["SPA_ADVANCED__LOG_FILE"] == "/tmp/elsewhere.log"


def test_we_never_touch_the_agents_own_rotating_log(spa_env, agent_ready, fake_popen, tmp_path,
                                                    monkeypatch):
    """It is rotated by the agent's own handler (5MB x 10), mid-run. Two rotators on one file
    would fight; ours must leave it strictly alone."""
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    tools = tmp_path / "tools-agent.log"
    tools.write_bytes(b"t" * 8192)          # far over our ceiling

    spa_env.start_spa("my_skill")

    assert tools.read_bytes() == b"t" * 8192, "the agent's own log must be untouched"
    assert not (tmp_path / "tools-agent.log.1").exists()


def test_a_failed_start_names_both_agent_logs(spa_env, agent_ready, fake_popen, monkeypatch,
                                              tmp_path):
    """An init failure after basicConfig lands in the agent's own log; anything above that line
    reaches only its stdout. The operator must be pointed at both."""
    monkeypatch.setattr(spa_env, "wait_for_health", lambda *a, **kw: False)
    monkeypatch.setattr(spa_env, "stop_spa", lambda: None)
    monkeypatch.setattr(spa_env.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError) as err:
        spa_env.start_spa("my_skill", retries=0)

    assert str(tmp_path / "skillberry-agent.log") in str(err.value)
    assert str(tmp_path / "tools-agent.log") in str(err.value)


# ---------------------------------------------------------------------------
# Initialization traces must survive (requirement 5)
# ---------------------------------------------------------------------------

def test_the_start_capture_is_truncated_not_appended(spa_env, fake_popen, tmp_path):
    """"wb" is what makes it self-limiting: it can never accumulate across runs."""
    log = tmp_path / "skillberry-store.log"
    capture = spa_env._start_capture_path(log)
    capture.write_text("stale content from a previous start")

    spa_env._start_detached(tmp_path, {}, log)

    assert fake_popen["mode"] == "wb"
    assert capture.read_text() == "", "a previous start's output must not accumulate"


def test_both_stdout_and_stderr_reach_the_start_capture(spa_env, fake_popen, tmp_path):
    """A crash writes to stderr — checking only stdout would miss the case this exists for."""
    log = tmp_path / "skillberry-store.log"
    spa_env._start_detached(tmp_path, {}, log)
    assert fake_popen["stdout"] is fake_popen["stderr"]
    assert fake_popen["stdout_name"] == str(spa_env._start_capture_path(log))


def test_a_successful_start_leaves_no_capture_behind(spa_env, tmp_path):
    capture = tmp_path / "skillberry-store.start.log"
    capture.write_text("make: Entering directory ...\n")
    assert spa_env._resolve_start_capture(capture, ok=True) is None
    assert not capture.exists(), "steady state must hold only the agreed logs"


def test_a_failed_start_keeps_the_capture_and_returns_its_tail(spa_env, tmp_path):
    capture = tmp_path / "skillberry-store.start.log"
    capture.write_text("make: *** No rule to make target 'srv.env'.  Stop.\n")

    tail = spa_env._resolve_start_capture(capture, ok=False)

    assert "No rule to make target" in tail
    assert capture.exists(), "the evidence for a failed start must not be deleted"


def test_the_failure_message_carries_the_make_output(spa_env, agent_ready, monkeypatch, tmp_path):
    """The whole point: a failure BEFORE the service is exec'd is visible only on make's stdout."""
    marker = "make: *** [run] Error 2 -- missing .stamps/srv.env"

    def fake(argv, **kw):
        kw["stdout"].write(marker.encode())
        kw["stdout"].flush()
        return type("P", (), {"pid": 7})()

    monkeypatch.setattr(spa_env.subprocess, "Popen", fake)
    monkeypatch.setattr(spa_env, "wait_for_health", lambda *a, **kw: False)
    monkeypatch.setattr(spa_env, "stop_spa", lambda: None)

    with pytest.raises(RuntimeError) as err:
        spa_env.start_spa("my_skill", retries=0)

    assert marker in str(err.value), "the make-level reason must reach the operator"


def test_a_later_success_cleans_up_after_an_earlier_failure(spa_env, agent_ready, fake_popen,
                                                            monkeypatch, tmp_path):
    outcomes = iter([False, True])
    monkeypatch.setattr(spa_env, "wait_for_health", lambda *a, **kw: next(outcomes))
    monkeypatch.setattr(spa_env, "stop_spa", lambda: None)
    monkeypatch.setattr(spa_env.time, "sleep", lambda *_: None)

    spa_env.start_spa("my_skill", retries=1)

    assert not spa_env._start_capture_path(tmp_path / "skillberry-agent.log").exists()


def test_an_unreadable_capture_does_not_mask_the_real_error(spa_env, tmp_path):
    capture = tmp_path / "skillberry-store.start.log"
    capture.mkdir()                                    # read_text raises OSError
    assert spa_env._resolve_start_capture(capture, ok=False) is None


# ---------------------------------------------------------------------------
# The env manager: same helper, called from run.sh (requirement 2)
# ---------------------------------------------------------------------------

def test_rotate_if_large_is_public(spa_env):
    """run.sh calls it by name out of process, so a rename must fail here rather than at runtime."""
    assert callable(getattr(spa_env, "rotate_if_large", None))
    assert not hasattr(spa_env, "_rotate_if_large"), "one public helper, not a private twin"


def test_the_env_manager_log_rotates_like_the_others(spa_env, tmp_path):
    log = tmp_path / "env_manager.log"
    log.write_bytes(b"e" * 4096)
    spa_env.rotate_if_large(log, max_bytes=1024, backups=3)
    assert (tmp_path / "env_manager.log.1").read_bytes() == b"e" * 4096
    assert not log.exists()


def test_it_is_callable_exactly_the_way_run_sh_calls_it(spa_env, tmp_path):
    """Out of process, from a FOREIGN cwd — the invocation contract, not the happy path.

    run.sh never cd's to $REPO (only its launch subshell does), so the insert it passes must be
    absolute. An earlier version of this test ran the subprocess with cwd=<repo root>, which made a
    cwd-relative insert pass here while failing for anyone invoking run.sh from elsewhere — and the
    `|| true` on that line swallowed the ImportError, so env_manager.log silently never rotated.
    Running from tmp_path is what makes this test able to catch that.
    """
    log = tmp_path / "env_manager.log"
    log.write_bytes(b"r" * 4096)
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import spa_env; spa_env.rotate_if_large(%r, max_bytes=1024)" %
            (str(SPA_ENV.parent), str(log)))

    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=tmp_path)                     # deliberately NOT the repo root

    assert r.returncode == 0, r.stderr
    assert (tmp_path / "env_manager.log.1").exists(), "rotation must happen in that subprocess"


def test_run_sh_anchors_the_import_path_and_reports_failure(spa_env):
    """The two properties of that run.sh line, checked on the script itself.

    This is the one place a source assertion is right: the defect is not in Python behaviour but in
    what the shell hands to it, and no unit test of spa_env can observe a bad path in run.sh.
    """
    run_sh = (SPA_ENV.parents[5]
              / "examples/tau2_custom/spa/run.sh").read_text()
    rotate_line = next(ln for ln in run_sh.splitlines() if "sys.path.insert" in ln
                       and "rotate" in run_sh.split(ln)[1][:120])

    assert "'$REPO/skills" in rotate_line, (
        "the insert must be $REPO-anchored; run.sh does not cd to $REPO, so a relative path breaks "
        "whenever it is invoked from another directory")

    block = run_sh.split("rotate_if_large('$ENV_LOG')")[1][:200]
    assert "|| true" not in block, (
        "a swallowed ImportError means env_manager.log silently never rotates")
    assert "WARNING" in block, "a rotation failure must be reported, not hidden"


# ---------------------------------------------------------------------------
# Reuse: a healthy service means do nothing at all (requirement 7)
# ---------------------------------------------------------------------------

def test_a_healthy_store_is_neither_restarted_nor_rotated(spa_env, monkeypatch, tmp_path):
    """The corruption case: rotating a log the live process holds open would leave it appending
    to a renamed inode while the fresh file stays empty."""
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "store_port", lambda: "8000")
    monkeypatch.setattr(spa_env, "health_ok", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"live process is writing this" + b"." * 4096)
    monkeypatch.setattr(spa_env, "STORE_LOG_FILE", str(log))
    launched = []
    monkeypatch.setattr(spa_env.subprocess, "Popen",
                        lambda *a, **kw: launched.append(a) or type("P", (), {"pid": 1})())

    spa_env.start_store()

    assert launched == [], "a healthy store must not be restarted"
    assert log.read_bytes().startswith(b"live process is writing this")
    assert not (tmp_path / "skillberry-store.log.1").exists(), "a live log must never be rotated"


def test_an_unhealthy_store_does_rotate_and_launch(spa_env, monkeypatch, tmp_path, fake_popen):
    """Positive control for the test above — the short-circuit must not disable rotation."""
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "store_port", lambda: "8000")
    monkeypatch.setattr(spa_env, "health_ok", lambda *a, **kw: False)
    monkeypatch.setattr(spa_env, "wait_for_health", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "port_owner_conflict", lambda *a, **kw: None)
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    d = tmp_path / "store"
    (d / ".git").mkdir(parents=True)
    monkeypatch.setattr(spa_env, "store_dir", lambda: d)
    monkeypatch.setattr(spa_env, "STORE_PID_FILE", str(tmp_path / "store.pid"))
    log = tmp_path / "skillberry-store.log"
    log.write_bytes(b"s" * 4096)
    monkeypatch.setattr(spa_env, "STORE_LOG_FILE", str(log))

    spa_env.start_store()

    assert (tmp_path / "skillberry-store.log.1").exists()
    assert f"SERVICE_LOG={log}" in fake_popen["cmd"]


def test_a_healthy_spa_serving_the_requested_skill_is_reused(spa_env, monkeypatch, tmp_path):
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "health_ok", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "_bound_skill_name", lambda: "my_skill")
    monkeypatch.setattr(spa_env, "LOG_MAX_BYTES", 1024)
    log = tmp_path / "skillberry-agent.log"
    log.write_bytes(b"live agent output" + b"." * 4096)
    monkeypatch.setattr(spa_env, "AGENT_LOG_FILE", str(log))
    launched = []
    monkeypatch.setattr(spa_env.subprocess, "Popen",
                        lambda *a, **kw: launched.append(a) or type("P", (), {"pid": 1})())

    spa_env.start_spa("my_skill")

    assert launched == [], "a healthy SPA must be reused, not restarted"
    assert log.read_bytes().startswith(b"live agent output")
    assert not (tmp_path / "skillberry-agent.log.1").exists(), "a live log must never be rotated"


def test_a_healthy_spa_bound_to_another_skill_refuses(spa_env, monkeypatch, tmp_path):
    """SPA binds ONE skill at start, so silent reuse would evaluate the wrong skill and report a
    reward for the wrong candidate."""
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "health_ok", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "_bound_skill_name", lambda: "some_other_skill")
    log = tmp_path / "skillberry-agent.log"
    log.write_bytes(b"live")
    monkeypatch.setattr(spa_env, "AGENT_LOG_FILE", str(log))

    with pytest.raises(RuntimeError) as err:
        spa_env.start_spa("my_skill")

    assert "some_other_skill" in str(err.value) and "stop_spa" in str(err.value)
    assert log.read_bytes() == b"live", "a refusal must not touch the log either"


def test_an_unreadable_bound_skill_is_reused_rather_than_refused(spa_env, monkeypatch, tmp_path):
    """None means 'cannot tell' (no /proc on macOS); refusing there would break that platform."""
    monkeypatch.setattr(spa_env, "load_env", lambda: None)
    monkeypatch.setattr(spa_env, "health_ok", lambda *a, **kw: True)
    monkeypatch.setattr(spa_env, "_bound_skill_name", lambda: None)
    monkeypatch.setattr(spa_env, "AGENT_LOG_FILE", str(tmp_path / "skillberry-agent.log"))
    launched = []
    monkeypatch.setattr(spa_env.subprocess, "Popen",
                        lambda *a, **kw: launched.append(a) or type("P", (), {"pid": 1})())

    spa_env.start_spa("my_skill")          # must not raise

    assert launched == []

# ---------------------------------------------------------------------------
# The provision-time patches
#
# These are what give the SERVICES their own rotation -- the only kind that can happen mid-run,
# since a live log can only be rotated by the process holding its fd. Driven against synthetic
# clones that mirror the pinned sources exactly.
# ---------------------------------------------------------------------------

AGENT_HANDLER_LINE = "file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=10)\n"
AGENT_BASICCONFIG = ("# Configure logger\n"
                     "logging.basicConfig(level=log_level, handlers=[console_handler, file_handler])\n")


@pytest.fixture
def agent_clone(tmp_path):
    """A minimal stand-in for the pinned skillberry-agent source the patches anchor on."""
    d = tmp_path / "skillberry-agent"
    d.mkdir()
    (d / "main.py").write_text(
        "import logging\nimport os\nfrom logging.handlers import RotatingFileHandler\n\n"
        'log_file = config.get("advanced__log_file")\n'
        "log_level = 'INFO'\n" + AGENT_HANDLER_LINE + AGENT_BASICCONFIG)
    return d


def test_the_agents_rotation_size_and_count_come_under_our_knobs(spa_env, agent_clone):
    """Upstream hardcodes 5MB x 10 with no config key, so tools-agent.log was the one log our
    variables could not reach: CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES=1048576 rotated the store every
    1MB while the agent kept rolling at 5MB."""
    spa_env._patch_agent_logging(agent_clone, "e359494")
    text = (agent_clone / "main.py").read_text()

    assert "maxBytes=5*1024*1024" not in text, "the hardcoded size must be gone"
    assert 'os.environ.get("CAPEVOLVE_SKILLBERRY_LOG_MAX_BYTES")' in text
    assert 'os.environ.get("CAPEVOLVE_SKILLBERRY_LOG_BACKUPS")' in text
    compile(text, "main.py", "exec")           # the patched source must still be valid Python


def test_the_agent_stops_duplicating_records_onto_stdout(spa_env, agent_clone):
    spa_env._patch_agent_logging(agent_clone, "e359494")
    text = (agent_clone / "main.py").read_text()
    assert "handlers=[file_handler]" in text
    assert "console_handler, file_handler" not in text, "the stdout duplicate is what grew unbounded"


def test_two_patches_to_one_file_do_not_shadow_each_other(spa_env, agent_clone):
    """Both agent patches live in main.py. With a single shared marker the second would be skipped,
    because the first one's marker is already in the file."""
    spa_env._patch_agent_logging(agent_clone, "e359494")
    text = (agent_clone / "main.py").read_text()
    assert spa_env._PATCH_MARKER in text
    assert spa_env._PATCH_MARKER_KNOBS in text, "the second patch must not be skipped by the first"


def test_re_provisioning_does_not_stack_duplicates(spa_env, agent_clone):
    """Idempotence, per patch — the agent carries two, and a shared marker would let the second be
    skipped or a keep-your-anchor replacement be appended twice on every provision."""
    spa_env._patch_agent_logging(agent_clone, "e359494")
    once = (agent_clone / "main.py").read_text()
    for _ in range(3):
        spa_env._patch_agent_logging(agent_clone, "e359494")
    assert (agent_clone / "main.py").read_text() == once, "re-provision must be a byte-for-byte no-op"


def test_every_marker_is_present_in_its_own_replacement(spa_env):
    """The assert inside _apply_patch guards this, but a mismatch would only surface at provision
    time on a real clone -- catch it here instead."""
    markers = [spa_env._PATCH_MARKER, spa_env._PATCH_MARKER_KNOBS]
    assert len(set(markers)) == len(markers), "markers must be distinct or patches shadow each other"
    assert all(m.startswith("# capevolve:") for m in markers), "keep them greppable in a clone"


def test_uvicorn_loggers_are_left_alone(spa_env, agent_clone, tmp_path):
    """Rerouting uvicorn's loggers LOST the access log, so neither patch may touch them.

    Every vMCP server builds uvicorn.Config(...), whose __init__ calls configure_logging() ->
    dictConfig, re-applying uvicorn's defaults process-wide. Combined with handlers=[] that left
    uvicorn.access with no handler AND no propagation: a GET returning 200 whose access line
    appeared in neither log. Untouched, those lines stay on stdout, which SERVICE_LOG captures and
    our start-time rotation bounds.
    """
    spa_env._patch_agent_logging(agent_clone, "e359494")
    assert "uvicorn" not in (agent_clone / "main.py").read_text(), (
        "the agent patch must not reconfigure uvicorn's loggers")

    store = tmp_path / "skillberry-store"
    (store / "src/skillberry_store/fast_api").mkdir(parents=True)
    (store / "src/skillberry_store/main.py").write_text(
        "import os\nimport sys\nimport signal\nimport atexit\n")
    server_py = store / "src/skillberry_store/fast_api/server.py"
    original = ('        log_config["loggers"]["uvicorn.access"][\n'
                '            "level"\n'
                '        ] = "DEBUG"  # Ensure all access logs are shown\n')
    server_py.write_text(original)

    spa_env._patch_store_logging(store, "0.2.1")

    assert server_py.read_text() == original, "server.py must not be modified at all"
    assert "RotatingFileHandler" in (store / "src/skillberry_store/main.py").read_text(), (
        "the handler in main.py is the part that works and must still be applied")


def test_a_moved_anchor_names_the_file_and_the_pinned_ref(spa_env, tmp_path):
    """A ref bump is the realistic trigger. Failing loudly at provision time is the whole point:
    silently skipping would leave a service whose log nothing rotates."""
    d = tmp_path / "agent-moved"
    d.mkdir()
    (d / "main.py").write_text("logging.basicConfig(level=log_level)\n")   # upstream changed it

    with pytest.raises(RuntimeError) as err:
        spa_env._patch_agent_logging(d, "deadbee")

    msg = str(err.value)
    assert "main.py" in msg and "deadbee" in msg
    assert "found 0" in msg
    assert "responsibility" in msg, "the message must say who owns the patch after a ref bump"


def test_an_ambiguous_anchor_refuses_rather_than_guessing(spa_env, tmp_path):
    d = tmp_path / "agent-dup"
    d.mkdir()
    (d / "main.py").write_text(AGENT_HANDLER_LINE + "\n" + AGENT_HANDLER_LINE)

    with pytest.raises(RuntimeError) as err:
        spa_env._patch_agent_logging(d, "e359494")

    assert "found 2" in str(err.value), "two candidates must not be patched blind"
