"""`live_push.sh --cleanup` must never be able to hold a benchmark job open.

WHAT BROKE

Run 36304767214 (`full_verified / spreadsheetbench`):

    3. Setup runner env            completed/failure     <- the real failure, ~3 min in
    4. Start live snapshot poller  completed/skipped
    5. Run suite                   completed/skipped
    6. Stop live snapshot poller   in_progress           <- still running 20+ minutes later

Step 4 was SKIPPED, so the poller never started and there was no live/ dir to delete and no
process to kill -- yet the stop step still hung, because it called `live_push.sh --cleanup`
unconditionally. Cleanup clones the `benchmark-history` branch, whose tip is ~1.4 GB across
24k files, and nothing bounded that clone or its push. Two costs followed: GitHub serves no
step log until the job ends, so the step-3 error was unreachable for as long as the hang
lasted (and was lost for good when the run was cancelled to force a flush); and the job's
`timeout-minutes: 1440` -- sized for a 912-task suite -- became the cleanup step's budget on
a single-leg self-hosted runner, so everything queued behind it could have waited 24h.

WHAT THIS PINS

1. No pidfile means the poller never ran: cleanup must return immediately and touch nothing.
2. A pidfile that names a dead pid must not turn into a wait -- the poller did run, so the
   push still has to happen, but promptly.
3. A git that never returns must not be able to outlive cleanup's own bound, and must stay
   NON-FATAL (rc 0 + a warning). This is the load-bearing half: a step killed by
   `timeout-minutes` is a FAILED step, which would fail the job over best-effort cleanup.
   The internal bound is what keeps the outer bound from ever being reached.
4. The workflow step declares a `timeout-minutes`, so the outer backstop cannot be dropped.
5. Cleanup still does its job: against a real (local) remote the live/ dir is deleted.

Deliberately pytest and not another `ci/benchmarks/lib/test_*.sh`: nothing in the workflows
runs those, so a regression there would be invisible.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIVE_PUSH = REPO / "ci" / "benchmarks" / "lib" / "live_push.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"

RUN_ID = "36304767214"
SLUG = "full_verified-spreadsheetbench"
SLUG_DIR = f"{RUN_ID}__{SLUG}"

GIT = shutil.which("git")


# --- harness ---------------------------------------------------------------------------------


def _stub_git(bindir: Path, body: str) -> Path:
    """A `git` earlier on PATH than the real one, logging every invocation."""
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "git"
    stub.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def _run_cleanup(tmp_path: Path, *, pidfile: Path, path: str, env_extra=None):
    """Run the real `live_push.sh --cleanup` and time it."""
    env = {
        "PATH": path,
        "RUNNER_TEMP": str(tmp_path / "runner_temp"),
        "GH_TOKEN": "dummy-token",
        "GITHUB_REPOSITORY": "skillberry-ai/cap-evolve",
        **(env_extra or {}),
    }
    (tmp_path / "runner_temp").mkdir(exist_ok=True)
    started = time.monotonic()
    proc = subprocess.run(
        ["bash", str(LIVE_PUSH), "--cleanup", RUN_ID, SLUG, str(pidfile)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    return proc, time.monotonic() - started


# --- 1. the no-pidfile path is a fast no-op --------------------------------------------------


def test_cleanup_without_a_pidfile_returns_immediately_and_touches_no_remote(tmp_path):
    """The exact shape of run 36304767214: step 4 skipped, so nothing to clean up."""
    log = tmp_path / "git.log"
    bindir = tmp_path / "bin"
    _stub_git(bindir, f'echo "$@" >> {log}\nexit 0\n')

    proc, elapsed = _run_cleanup(
        tmp_path, pidfile=tmp_path / "never-written.pid", path=f"{bindir}:/usr/bin:/bin"
    )

    assert proc.returncode == 0, f"a no-op cleanup must succeed:\n{proc.stdout}\n{proc.stderr}"
    assert elapsed < 1.0, f"cleanup took {elapsed:.1f}s with nothing to clean up"
    assert not log.exists(), (
        "cleanup ran git although the poller never started -- that unconditional clone of a "
        f"~1.4 GB branch is the hang in #547. git calls: {log.read_text()}"
    )


def test_cleanup_without_a_pidfile_does_not_even_need_git(tmp_path):
    """Nothing to clean up must mean nothing to run -- not even a tool lookup that can fail."""
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    proc, elapsed = _run_cleanup(
        tmp_path, pidfile=tmp_path / "never-written.pid", path=f"{empty}:/usr/bin:/bin"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert elapsed < 1.0, f"took {elapsed:.1f}s"


# --- 2. a stale pidfile is not a wait --------------------------------------------------------


def _dead_pid() -> int:
    """A pid that has certainly exited: our own short-lived child."""
    p = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
    p.wait()
    return p.pid


def test_cleanup_with_a_stale_pidfile_naming_a_dead_pid_returns_promptly(tmp_path):
    """The poller DID run, so the push must still happen -- but no waiting on a corpse."""
    log = tmp_path / "git.log"
    bindir = tmp_path / "bin"
    _stub_git(bindir, f'echo "$@" >> {log}\nexit 0\n')
    pidfile = tmp_path / "live_push.pid"
    pidfile.write_text(f"{_dead_pid()}\n", encoding="utf-8")

    proc, elapsed = _run_cleanup(tmp_path, pidfile=pidfile, path=f"{bindir}:/usr/bin:/bin")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert elapsed < 10.0, f"a dead pid turned into a {elapsed:.1f}s wait"
    assert log.exists() and "clone" in log.read_text(), (
        "the poller had started, so its live/ dir must still be deleted; git was never called:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    assert not pidfile.exists(), "the pidfile must be removed so a retry stays a no-op"


def test_cleanup_kills_a_live_poller(tmp_path):
    """The kill moved out of the workflow step and into here, so it needs coverage here.

    It must also happen BEFORE the delete: a poller left alive can push live/<slug_dir> back.
    """
    log = tmp_path / "git.log"
    bindir = tmp_path / "bin"
    # The stub sleeps, so the kill has to have happened before git returned, not after.
    _stub_git(bindir, f'echo "$@" >> {log}\nsleep 2\nexit 1\n')
    poller = subprocess.Popen(["/bin/sh", "-c", "exec sleep 600"])
    pidfile = tmp_path / "live_push.pid"
    pidfile.write_text(f"{poller.pid}\n", encoding="utf-8")
    try:
        proc, _ = _run_cleanup(tmp_path, pidfile=pidfile, path=f"{bindir}:/usr/bin:/bin")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert poller.poll() is not None or poller.wait(timeout=5) is not None, (
            "the poller survived cleanup and can push its live/ dir back after the delete"
        )
    finally:
        if poller.poll() is None:
            poller.kill()
            poller.wait()


# --- 3. a hanging git cannot outlive cleanup's own bound -------------------------------------


HANG = 'echo "$@" >> {log}\necho "GIT_TERMINAL_PROMPT=$GIT_TERMINAL_PROMPT" >> {log}\nexec sleep 600\n'


def test_a_git_that_never_returns_is_bounded_and_non_fatal(tmp_path):
    """This is the 24h exposure: unbounded git inside a step with `timeout-minutes: 1440`."""
    log = tmp_path / "git.log"
    bindir = tmp_path / "bin"
    _stub_git(bindir, HANG.format(log=log))
    pidfile = tmp_path / "live_push.pid"
    pidfile.write_text(f"{_dead_pid()}\n", encoding="utf-8")

    proc, elapsed = _run_cleanup(
        tmp_path, pidfile=pidfile, path=f"{bindir}:/usr/bin:/bin",
        env_extra={"LIVE_PUSH_GIT_TIMEOUT": "3"},
    )

    assert elapsed < 40.0, f"a hung git held cleanup for {elapsed:.1f}s despite a 3s git bound"
    assert proc.returncode == 0, (
        "a failed cleanup must stay non-fatal (`::warning::`, never an error):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_cleanup_never_lets_git_stop_for_a_credential_prompt(tmp_path):
    """A prompt on a runner with no tty is an indefinite stall, not an error."""
    log = tmp_path / "git.log"
    bindir = tmp_path / "bin"
    _stub_git(bindir, HANG.format(log=log))
    pidfile = tmp_path / "live_push.pid"
    pidfile.write_text(f"{_dead_pid()}\n", encoding="utf-8")

    _run_cleanup(tmp_path, pidfile=pidfile, path=f"{bindir}:/usr/bin:/bin",
                 env_extra={"LIVE_PUSH_GIT_TIMEOUT": "3"})

    assert log.exists(), "git was never invoked"
    assert "GIT_TERMINAL_PROMPT=0" in log.read_text(), (
        f"git can still prompt for credentials:\n{log.read_text()}"
    )


def test_cleanups_worst_case_fits_inside_the_step_bound():
    """The internal bound must be the one that fires, not the workflow's.

    A step killed by `timeout-minutes` is a FAILED step, and a failed best-effort cleanup must
    not fail the job -- so cleanup's own worst case has to sit strictly inside the step's
    budget. Cleanup makes at most two network git calls per attempt (clone, then push), each
    capped at LIVE_PUSH_GIT_TIMEOUT, plus the inter-attempt backoff.
    """
    git_timeout = _default_git_timeout()
    attempts = _cleanup_attempts()
    worst = attempts * (2 * git_timeout + 3)
    budget = _step_timeout_minutes() * 60
    assert worst < budget, (
        f"cleanup's worst case is {worst}s ({attempts} attempt(s) x 2 git calls x "
        f"{git_timeout}s), which does not fit inside the step's {budget}s `timeout-minutes` -- "
        "so the step would be killed, which fails the job over best-effort cleanup"
    )


def _default_git_timeout() -> int:
    src = LIVE_PUSH.read_text(encoding="utf-8")
    m = re.search(r"LIVE_PUSH_GIT_TIMEOUT:-(\d+)", src)
    assert m, "live_push.sh declares no default per-git-call timeout"
    return int(m.group(1))


def _cleanup_attempts() -> int:
    src = LIVE_PUSH.read_text(encoding="utf-8")
    m = re.search(r"LIVE_PUSH_CLEANUP_ATTEMPTS:-(\d+)", src)
    assert m, "cleanup does not bound its clone/push attempt count"
    return int(m.group(1))


# --- 4. the workflow keeps its outer backstop ------------------------------------------------


def _stop_step() -> str:
    """The `Stop live snapshot poller` step, sliced out of benchmarks.yml.

    Parsed with a regex rather than PyYAML on purpose: `core[dev]` ships pytest/openpyxl/
    pandas and nothing else, and a test that skips itself for a missing dep is worse than no
    test (see test_spreadsheetbench_full_verified_tier.py for the same note).
    """
    src = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"\n(\s*)- name: Stop live snapshot poller\n", src)
    assert m, "the `Stop live snapshot poller` step is gone from benchmarks.yml"
    indent = m.group(1)
    rest = src[m.end():]
    nxt = re.search(rf"^{indent}- name: ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _step_timeout_minutes() -> int:
    m = re.search(r"^\s*timeout-minutes:\s*(\d+)\s*$", _stop_step(), re.M)
    assert m, (
        "the `Stop live snapshot poller` step declares no `timeout-minutes`. Without it the "
        "step inherits the job's 1440 and best-effort cleanup can hold the self-hosted runner "
        "for a day (#547)."
    )
    return int(m.group(1))


def test_the_stop_poller_step_is_bounded():
    assert 1 <= _step_timeout_minutes() <= 5, (
        f"cleanup's bound is {_step_timeout_minutes()} min; it must never be able to outlive "
        "the work it cleans up after"
    )


def test_the_stop_poller_step_stays_non_fatal():
    """Acceptance criterion from #547: cleanup failures must not fail the job."""
    step = _stop_step()
    assert "::warning::" in step, f"the non-fatal warning was replaced:\n{step}"
    assert "::error::" not in step, f"cleanup became fatal:\n{step}"


def test_the_workflow_hands_cleanup_the_pidfile_it_guards_on():
    """The never-started fast path only fires in CI if the pidfile is an ARGUMENT to
    `--cleanup` -- merely mentioning it elsewhere in the step is not enough."""
    step = _stop_step()
    m = re.search(r"live_push\.sh --cleanup(.*?)(?<!\\)\n", step, re.S)
    assert m, f"the stop step no longer calls `live_push.sh --cleanup`:\n{step}"
    argv = m.group(1).replace("\\\n", " ")
    assert ".pid" in argv, (
        "`--cleanup` is not given the poller's pidfile, so it cannot tell a never-started "
        f"poller from a finished one:\n{argv}"
    )


def _start_step() -> str:
    src = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"\n(\s*)- name: Start live snapshot poller\n", src)
    assert m, "the `Start live snapshot poller` step is gone from benchmarks.yml"
    rest = src[m.end():]
    nxt = re.search(rf"^{m.group(1)}- name: ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def test_the_two_steps_agree_on_the_pidfile_path():
    """Cross-file drift here is silent and total: the stop step would see no pidfile for a
    poller that IS running, skip cleanup, and leave the live/ dir behind forever."""
    pat = re.compile(r'\$RUNNER_TEMP/live_push_[^"]*\.pid')
    written = set(pat.findall(_start_step()))
    read = set(pat.findall(_stop_step()))
    assert written and read, f"written={written} read={read}"
    assert written == read, (
        f"the poller writes {written} but cleanup looks for {read}"
    )


# --- 5. cleanup still cleans up --------------------------------------------------------------


@pytest.mark.skipif(GIT is None, reason="git not installed")
def test_cleanup_still_deletes_the_live_dir(tmp_path):
    """Bounding must not quietly turn cleanup into a no-op. Real git, local remote."""
    genv = {**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def g(cwd, *args):
        p = subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True, env=genv)
        assert p.returncode == 0, f"git {args}: {p.stdout}{p.stderr}"

    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    seed.mkdir()
    g(seed, "init", "-q", "-b", "benchmark-history")
    keep = seed / "live" / "99__other-bench" / "data"
    keep.mkdir(parents=True)
    (keep / "index.json").write_text("{}", encoding="utf-8")
    mine = seed / "live" / SLUG_DIR / "data"
    mine.mkdir(parents=True)
    (mine / "index.json").write_text("{}", encoding="utf-8")
    g(seed, "add", "-A")
    g(seed, "commit", "-qm", "seed")
    g(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))

    pidfile = tmp_path / "live_push.pid"
    pidfile.write_text(f"{_dead_pid()}\n", encoding="utf-8")
    proc, elapsed = _run_cleanup(
        tmp_path, pidfile=pidfile, path=os.environ["PATH"],
        env_extra={"LIVE_REMOTE": str(origin), "HOME": str(tmp_path),
                   "GIT_CONFIG_NOSYSTEM": "1"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    listing = subprocess.run([GIT, "ls-tree", "-r", "--name-only", "benchmark-history"],
                             cwd=origin, capture_output=True, text=True, env=genv).stdout
    assert f"live/{SLUG_DIR}/" not in listing, f"the live dir was not deleted:\n{listing}\n{proc.stdout}"
    assert "live/99__other-bench/data/index.json" in listing, (
        f"cleanup deleted another run's live dir:\n{listing}"
    )
