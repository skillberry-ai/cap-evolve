"""#118: tell a stalled/hung run from an idle one from a finished one.

The state machine under test (``eventstream.classify``):

    done      finalize sealed the test → terminal, nothing downgrades it
    crashed   the owning process is PROVABLY gone and the run never finalized
    stalled   silent longer than THIS RUN's own derived expectation, process alive/unknown
    live      everything else, including long silences a slow run has earned

The test that matters most is :func:`test_a_slow_but_healthy_run_is_never_called_hung`:
a false "hung" is worse than no signal at all, because the user's reaction is to kill a
run that was working.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cap_evolve import eventstream  # noqa: E402
from cap_evolve.cli import _cmd_tail  # noqa: E402


def _run_dir(tmp_path, gaps_seconds, *, silent_for=0.0, finalize=False,
             pid=None, host=None, name="run_t", started=None) -> Path:
    """A run dir whose events are spaced by ``gaps_seconds`` and whose events file was
    last touched ``silent_for`` seconds ago. mtime is set explicitly so a stall of hours
    is testable in milliseconds.

    ``started`` writes that value as the marker's start stamp (pid-reuse detection);
    omitted means a legacy marker with no ``started`` at all."""
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    last = now - silent_for
    # Walk the timestamps backwards from `last` so the newest event is `silent_for` old.
    ts, cursor = [], last
    for g in reversed(list(gaps_seconds)):
        ts.append(cursor)
        cursor -= g
    ts.append(cursor)
    ts.reverse()
    lines = [json.dumps({"t": t, "kind": "evaluate", "split": "val"}) for t in ts]
    if finalize:
        lines.append(json.dumps({"t": last, "kind": "finalize", "test_reward": 1.0}))
    (root / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.utime(root / "events.jsonl", (last, last))
    if pid is not None:
        import socket
        marker = {"pid": pid, "host": host or socket.gethostname()}
        if started is not None:
            marker["started"] = started
        (root / "run.pid").write_text(json.dumps(marker), encoding="utf-8")
    return root


def _classify(root) -> str:
    return eventstream.classify(eventstream.liveness_facts(root))


# ---- the four states -------------------------------------------------------

def test_working_run_is_live(tmp_path):
    root = _run_dir(tmp_path, [30.0, 30.0, 30.0], silent_for=5.0, pid=os.getpid())
    assert _classify(root) == "live"
    assert "working" in eventstream.describe_status(eventstream.liveness_facts(root))


def test_a_quiet_fast_run_whose_process_lives_is_stalled(tmp_path):
    """Fast events then long silence, owner alive → stalled, not crashed, not done."""
    root = _run_dir(tmp_path, [1.0, 1.0, 1.0], silent_for=3600.0, pid=os.getpid())
    facts = eventstream.liveness_facts(root)
    assert facts["alive"] is True
    assert eventstream.classify(facts) == "stalled"
    detail = eventstream.describe_status(facts)
    assert "STALLED" in detail and "still alive" in detail


def test_a_run_whose_process_is_gone_is_crashed_not_live(tmp_path):
    """The bug in the issue: 1 candidate then a crash showed 'live' forever."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [1.0, 1.0], silent_for=120.0, pid=dead.pid)
    facts = eventstream.liveness_facts(root)
    assert facts["alive"] is False
    assert eventstream.classify(facts) == "crashed"
    assert "CRASHED" in eventstream.describe_status(facts)


def test_a_finalized_run_is_done_even_when_ancient_and_processless(tmp_path):
    """Degrades sanely for a finished run: done outranks both stall and crash."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [1.0, 1.0], silent_for=86_400.0 * 30, finalize=True,
                    pid=dead.pid)
    assert _classify(root) == "done"
    assert "done" in eventstream.describe_status(eventstream.liveness_facts(root))


# ---- THE critical negative case -------------------------------------------

def test_a_slow_but_healthy_run_is_never_called_hung(tmp_path):
    """A τ²-bench-shaped run: 20-minute steps. 25 minutes of silence is NORMAL for it.

    A fixed 5-minute idle timeout (the old heuristic) would call this hung and invite
    the user to kill a working run. The derived threshold must not.
    """
    twenty_min = 20 * 60.0
    root = _run_dir(tmp_path, [twenty_min] * 3, silent_for=25 * 60.0, pid=os.getpid())
    facts = eventstream.liveness_facts(root)
    assert facts["silence"] > 300.0            # the OLD fixed 5-minute rule would fire
    assert eventstream.classify(facts) == "live"                # the new one does not
    assert facts["threshold"] == pytest.approx(twenty_min * eventstream.STALL_SLACK)
    # …and it still fires eventually: the bar rises, it does not vanish.
    late = _run_dir(tmp_path, [twenty_min] * 3, silent_for=twenty_min * 4,
                    pid=os.getpid(), name="run_late")
    assert _classify(late) == "stalled"


def test_a_toy_run_still_gets_the_floor(tmp_path):
    """The other direction: millisecond gaps must NOT derive a millisecond threshold."""
    root = _run_dir(tmp_path, [0.04, 0.04], silent_for=30.0, pid=os.getpid())
    facts = eventstream.liveness_facts(root)
    assert facts["threshold"] == eventstream.STALL_FLOOR_SECONDS
    assert eventstream.classify(facts) == "live"


# ---- the false positive the #218 review caught -----------------------------

def test_a_healthy_run_in_its_FIRST_slow_step_is_not_stalled(tmp_path):
    """The review's blocking #1, and the shape that matters most.

    A real run opens with a burst of sub-second events and only then makes its first
    genuinely slow optimizer call. There is no COMPLETED slow gap to derive a bar from,
    so the floor is what judges it — and at 300s every run whose first step ran over five
    minutes was reported `stalled` while its owner was alive in `ps`. Nothing here is
    pre-seeded with completed slow gaps; that pre-seeding is exactly what hid the bug.
    """
    for elapsed in (301.0, 900.0, 1800.0, 3000.0):
        root = _run_dir(tmp_path, [0.2, 0.1], silent_for=elapsed, pid=os.getpid(),
                        name=f"run_first_{int(elapsed)}")
        facts = eventstream.liveness_facts(root)
        assert facts["slowest_gap"] < 1.0, "no completed slow gap, by construction"
        assert facts["alive"] is True
        assert eventstream.classify(facts) == "live", (
            f"a live run {elapsed}s into its first slow step must not read stalled")
    # A single event and nothing since (review probe B) is the same shape.
    solo = _run_dir(tmp_path, [], silent_for=600.0, pid=os.getpid(), name="run_solo")
    assert _classify(solo) == "live"
    # It is still not a wait-forever: past the floor, a fast run that really wedged trips.
    wedged = _run_dir(tmp_path, [0.2, 0.1], silent_for=eventstream.STALL_FLOOR_SECONDS + 60,
                      pid=os.getpid(), name="run_wedged")
    assert _classify(wedged) == "stalled"


def test_folding_the_open_gap_into_the_bar_would_never_fire(tmp_path):
    """Why the floor was raised instead of taking the review's suggested fix.

    The suggestion was to fold the CURRENT silence into the ``max`` that derives the bar.
    But the bar is what that same silence is compared against, so with any factor >= 1 the
    bar outruns the silence forever and ``stalled`` becomes unreachable; with a factor < 1
    the bar collapses onto the floor and the fold does nothing. Either way it is not a fix,
    which is why the conservative prior (a floor no legitimate first step exceeds) is.
    """
    for factor in (eventstream.STALL_SLACK, 1.0):
        silence = 0.0
        for _ in range(600):  # ten hours, one minute at a time
            silence += 60.0
            assert silence <= max(300.0, factor * silence), "would have fired"
    for factor in (0.5, 0.1):
        silence = 10_000.0
        assert max(300.0, factor * silence) != 300.0 or silence > 3000.0
        # …collapses to the bare floor for any silence under 300/factor.
        assert max(300.0, factor * 100.0) == 300.0


def test_a_live_writer_with_a_stale_dead_marker_is_not_crashed(tmp_path):
    """The review's blocking #2 / probe T: ``run.pid`` is never deleted, so a reused run
    dir can hold a dead pid from a previous attempt while the current writer (the
    per-phase skill chain writes no marker at all) is actively appending. That read
    `crashed` on a run with silence=0.0s — a demonstrably live run declared dead."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [1.0, 1.0], silent_for=0.0, pid=dead.pid, name="run_reused")
    facts = eventstream.liveness_facts(root)
    assert facts["alive"] is False and facts["silence"] < 5.0
    assert eventstream.classify(facts) == "live", "a run writing NOW is not dead"
    # The corroboration is silence, not trust: once the log really stops, crashed lands.
    gone = _run_dir(tmp_path, [1.0, 1.0], silent_for=120.0, pid=dead.pid, name="run_gone")
    assert _classify(gone) == "crashed"


def test_a_reused_pid_is_dead_because_started_disagrees(tmp_path):
    """``started`` was written and never read. A marker naming a pid that now belongs to a
    DIFFERENT, later-started process must read crashed — the old run really is gone."""
    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        # Marker claims the owner began an hour before this process actually did.
        root = _run_dir(tmp_path, [1.0], silent_for=600.0, pid=live.pid,
                        started=time.time() - 3600.0, name="run_recycled")
        facts = eventstream.liveness_facts(root)
        if eventstream._proc_start_time(live.pid) is None:
            pytest.skip("no usable `ps -o lstart=` on this platform")
        assert facts["alive"] is False, "same pid, a process that started later"
        assert eventstream.classify(facts) == "crashed"
        # The genuine owner — marker written just after the process began — stays alive.
        same = _run_dir(tmp_path, [1.0],
                        silent_for=eventstream.STALL_FLOOR_SECONDS + 60, pid=live.pid,
                        started=time.time(), name="run_genuine")
        assert eventstream.liveness_facts(same)["alive"] is True
        assert _classify(same) == "stalled"  # alive but quiet, never crashed
    finally:
        live.kill()
        live.wait()


def test_a_zombie_owner_is_stalled_not_crashed(tmp_path):
    """``os.kill(pid, 0)`` succeeds on a zombie, so it reads alive → stalled. Correct: a
    reaped-but-unwaited child is not proof the run's work is gone."""
    z = subprocess.Popen([sys.executable, "-c", "pass"])
    z.poll()  # do NOT wait() — leave it un-reaped so it stays a zombie
    try:
        root = _run_dir(tmp_path, [1.0], silent_for=7200.0, pid=z.pid, name="run_zombie")
        facts = eventstream.liveness_facts(root)
        assert facts["alive"] is not False   # a zombie is never proof of a dead run
        assert eventstream.classify(facts) in ("stalled", "live")
    finally:
        z.wait()


def test_a_marker_without_started_still_works(tmp_path):
    """Backwards compatibility: a marker written by an older `cap-evolve run` has no
    ``started`` field, and must fall back to pid-only rather than guessing."""
    root = _run_dir(tmp_path, [1.0], silent_for=600.0, pid=os.getpid(), name="run_legacy")
    assert "started" not in json.loads((root / "run.pid").read_text())
    assert eventstream.liveness_facts(root)["alive"] is True


def test_threshold_uses_the_slowest_gap_not_the_mean(tmp_path):
    """A run alternating 1s evals with 20-minute optimizer calls has a small mean; a
    mean-based bar would fire during every optimizer call."""
    gaps = [1.0, 1200.0, 1.0, 1200.0]
    assert eventstream.stall_threshold(gaps) == pytest.approx(1200.0 * 3)
    mean = sum(gaps) / len(gaps)
    assert eventstream.stall_threshold(gaps) > mean * eventstream.STALL_SLACK


# ---- liveness signal edge cases -------------------------------------------

def test_no_pid_file_means_unknown_never_crashed(tmp_path):
    """The per-phase skill-chain workflow has no single owning process; its runs must
    get the time verdict only, never a fabricated 'crashed'."""
    root = _run_dir(tmp_path, [1.0, 1.0], silent_for=3600.0)  # no run.pid
    facts = eventstream.liveness_facts(root)
    assert facts["alive"] is None
    assert eventstream.classify(facts) == "stalled"   # quiet, but not declared dead
    assert "not reporting a pid" in eventstream.describe_status(facts)


def test_a_pid_from_another_host_is_unknown_not_dead(tmp_path):
    """Someone else's process table is not ours to read: a shared-filesystem run must
    not be reported crashed just because its pid doesn't exist here."""
    root = _run_dir(tmp_path, [1.0], silent_for=10.0, pid=999_999, host="some-other-box")
    assert eventstream.liveness_facts(root)["alive"] is None
    assert _classify(root) == "live"


def test_malformed_pid_file_and_malformed_timestamps_do_not_raise(tmp_path):
    root = tmp_path / "run_bad"
    root.mkdir()
    (root / "events.jsonl").write_text(
        json.dumps({"t": "not-a-number", "kind": "evaluate"}) + "\n"
        + json.dumps({"t": None, "kind": "step"}) + "\n"
        + "{ not json\n", encoding="utf-8")
    (root / "run.pid").write_text("<<not json>>", encoding="utf-8")
    facts = eventstream.liveness_facts(root)
    assert facts["alive"] is None and facts["events"] == 0
    assert eventstream.classify(facts) in ("live", "stalled")


def test_missing_events_file_is_live_not_stalled(tmp_path):
    """A run dir that exists but hasn't spoken yet is starting up, not hung."""
    root = tmp_path / "run_new"
    root.mkdir()
    facts = eventstream.liveness_facts(root)
    assert facts["silence"] is None
    assert eventstream.classify(facts) == "live"


def test_env_override_wins_over_the_derived_threshold(tmp_path, monkeypatch):
    """Configurable: a user who knows their workload can pin the number."""
    monkeypatch.setenv(eventstream.STALL_ENV, "60")
    root = _run_dir(tmp_path, [1200.0, 1200.0], silent_for=120.0, pid=os.getpid())
    facts = eventstream.liveness_facts(root)
    assert facts["threshold"] == 60.0
    assert eventstream.classify(facts) == "stalled"
    monkeypatch.setenv(eventstream.STALL_ENV, "garbage")   # bad value → derive
    assert eventstream.liveness_facts(root)["threshold"] == pytest.approx(3600.0)


# ---- terminal surface: cap-evolve tail ------------------------------------

def test_tail_exits_4_and_says_stalled(tmp_path, capsys):
    """A hung run must not exit 0 with a silence that reads like success."""
    root = _run_dir(tmp_path, [0.01, 0.01],
                    silent_for=eventstream.STALL_FLOOR_SECONDS * 2, pid=os.getpid(),
                    name="run_hung")
    rc = _cmd_tail([str(root), "--from-start"])
    err = capsys.readouterr().err
    assert rc == 4, err
    assert "STALLED" in err and "no events for" in err


def test_tail_exits_5_and_says_crashed(tmp_path, capsys):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [0.01], silent_for=600.0, pid=dead.pid, name="run_dead")
    rc = _cmd_tail([str(root), "--from-start"])
    err = capsys.readouterr().err
    assert rc == 5, err
    assert "CRASHED" in err


def test_tail_exits_5_on_a_dead_run_WITHOUT_from_start_too(tmp_path, capsys):
    """The review's blocking #4, second half. Without ``--from-start`` nothing new ever
    arrives on a dead run, so `last` stayed None, the liveness probe never ran, and the
    crash verdict — the headline feature — degraded to the OLD ambiguous exit 3. `crashed`
    is proof-based, so it must not depend on whether this process happened to see a line."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [0.01], silent_for=600.0, pid=dead.pid, name="run_dead2")
    rc = _cmd_tail([str(root), "--idle-timeout", "30"])
    err = capsys.readouterr().err
    assert rc == 5, err            # was 3: "timed out … with no events"
    assert "CRASHED" in err and "timed out" not in err


def test_tail_idle_timeout_zero_still_exits_on_a_provably_dead_run(tmp_path, capsys):
    """`--idle-timeout 0` is documented as "wait forever" — for a run that might still
    speak. On a run whose owner is provably gone there is nothing left to wait for, and
    the old code hung indefinitely instead of reporting the crash."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    root = _run_dir(tmp_path, [0.01], silent_for=600.0, pid=dead.pid, name="run_dead0")
    done: list = []

    def watch():
        done.append(_cmd_tail([str(root), "--idle-timeout", "0"]))

    t = threading.Thread(target=watch, daemon=True)
    t.start()
    t.join(timeout=30)
    assert not t.is_alive(), "tail --idle-timeout 0 hung on a provably dead run"
    assert done == [5], capsys.readouterr().err


def test_tail_idle_timeout_zero_still_waits_forever_when_nothing_is_proven_dead(tmp_path):
    """The other direction: no marker → `alive is None` → no proof → keep waiting. The
    stall branch must stay gated on having seen an event, or a run that has not started
    talking yet would be declared wedged."""
    root = tmp_path / "run_quiet"
    root.mkdir()
    (root / "events.jsonl").write_text("", encoding="utf-8")
    t = threading.Thread(target=lambda: _cmd_tail([str(root), "--idle-timeout", "0"]),
                         daemon=True)
    t.start()
    t.join(timeout=6)
    assert t.is_alive(), "must still wait forever when nothing is provably dead"


def test_tail_exits_0_and_says_done_for_a_finalized_run(tmp_path, capsys):
    root = _run_dir(tmp_path, [0.01], silent_for=7200.0, finalize=True, name="run_fin")
    assert _cmd_tail([str(root), "--from-start"]) == 0
    err = capsys.readouterr().err
    assert "done" in err and "STALLED" not in err and "CRASHED" not in err


def test_tail_no_stall_check_keeps_following(tmp_path, capsys):
    """Opt-out: a user who wants the old wait-forever behavior gets it."""
    root = _run_dir(tmp_path, [0.01], silent_for=3600.0, pid=os.getpid(),
                    name="run_optout")

    def finish():
        time.sleep(0.4)
        with (root / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": "finalize",
                                 "test_reward": 1.0}) + "\n")

    threading.Thread(target=finish, daemon=True).start()
    assert _cmd_tail([str(root), "--from-start", "--no-stall-check"]) == 0
    assert "FINALIZE" in capsys.readouterr().out


def test_tail_does_not_stall_out_a_slow_but_healthy_run(tmp_path, capsys):
    """End to end through the CLI: the negative case must hold at the surface too."""
    root = _run_dir(tmp_path, [20 * 60.0] * 3, silent_for=25 * 60.0, pid=os.getpid(),
                    name="run_slow")

    def finish():
        time.sleep(0.5)
        with (root / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": "finalize",
                                 "test_reward": 1.0}) + "\n")

    threading.Thread(target=finish, daemon=True).start()
    rc = _cmd_tail([str(root), "--from-start"])
    err = capsys.readouterr().err
    assert rc == 0, err
    assert "STALLED" not in err


def test_tail_attaching_mid_run_uses_the_whole_log_not_just_what_it_streamed(tmp_path,
                                                                            capsys):
    """`tail` without --from-start prints only new events, but the stall bar must still
    come from the WHOLE log — otherwise attaching to a 20-min-per-step run sees no gaps,
    falls back to the 300s floor, and reports a healthy run hung."""
    root = _run_dir(tmp_path, [20 * 60.0] * 3, silent_for=25 * 60.0, pid=os.getpid(),
                    name="run_attach")

    def finish():
        time.sleep(0.5)
        with (root / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": "finalize",
                                 "test_reward": 1.0}) + "\n")

    threading.Thread(target=finish, daemon=True).start()
    rc = _cmd_tail([str(root)])           # NOT --from-start: history is skipped
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert "STALLED" not in err
    assert "eval val" not in out          # history really was skipped


def test_tail_still_returns_3_when_nothing_ever_arrives(tmp_path, capsys):
    """--idle-timeout keeps bounding the wait for the FIRST event (unchanged, #116)."""
    assert _cmd_tail([str(tmp_path / "run_pending"), "--idle-timeout", "0.3"]) == 3
    assert "timed out" in capsys.readouterr().err


# ---- one shared source of truth -------------------------------------------

def test_run_writes_a_pid_marker_so_liveness_is_knowable(tmp_path):
    """`cap-evolve run` must record its pid; without it crash detection is impossible.

    The source-text half is unavoidable (driving the real `run` needs a skill tree, which
    ``test_e2e_slice`` owns) but it is no longer the whole test: the review's non-blocking
    #9 notes the old grep would pass with the marker written to the WRONG DIRECTORY. So the
    exact expression `cli.py` writes is evaluated here and read back through the real
    ``_owner_alive``, pinning both the field set and the location liveness looks in.
    """
    import socket
    src = Path(eventstream.__file__).with_name("cli.py").read_text(encoding="utf-8")
    assert '(workdir / run_dir / "run.pid").write_text(' in src, "marker moved out of the run dir"
    assert "os.getpid()" in src and "gethostname()" in src and '"started": time.time()' in src

    run_dir = tmp_path / "run_marker"
    run_dir.mkdir()
    (run_dir / "run.pid").write_text(json.dumps(
        {"pid": os.getpid(), "host": socket.gethostname(), "started": time.time()}),
        encoding="utf-8")
    assert eventstream._owner_alive(run_dir) is True     # found where `run` puts it
    assert eventstream._owner_alive(tmp_path) is None    # and nowhere else


def test_dashboard_classifies_through_the_shared_helper_not_its_own_rule():
    """The surfaces cannot disagree because there is only one classifier.

    Asserted on the source rather than by import identity: the dashboard package is a
    sibling tree, and what must hold is that it *routes through* eventstream and owns
    no threshold of its own — a second copy of the rule is the bug (#118 exists because
    the SSE route and ``_status`` each had their own).
    """
    src = (Path(__file__).resolve().parents[2] / "dashboard" / "backend"
           / "capevolve_dashboard" / "runs.py").read_text(encoding="utf-8")
    assert "eventstream.classify" in src and "eventstream.liveness_facts" in src
    for forked in ("300", "STALL_FLOOR", "timedelta", "mtime >"):
        assert forked not in src, f"dashboard re-derives the stall rule ({forked})"
