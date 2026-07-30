"""#118: the hub/DeepDive must distinguish stalled/crashed from live and from done.

Every verdict here comes from ``cap_evolve.eventstream`` — the same functions
``cap-evolve tail`` uses — so a test asserting the API payload is also asserting that
the terminal would say the same thing about the same run dir.
"""
import json
import os
import subprocess
import sys
import threading
import time

from conftest import BASE_EVENTS


def _age(rd, seconds, *, pid=None, host=None):
    """Backdate the run's events.jsonl mtime and (optionally) name an owning process."""
    last = time.time() - seconds
    os.utime(rd.events_path, (last, last))
    if pid is not None:
        import socket
        (rd.root / "run.pid").write_text(json.dumps(
            {"pid": pid, "host": host or socket.gethostname()}), encoding="utf-8")


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


# ---- _status ---------------------------------------------------------------

def test_a_silent_unfinalized_run_is_stalled_not_live(tmp_base, make_run):
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    _age(rd, 3600.0, pid=os.getpid())          # events seconds apart, silent an hour
    rows = runs.list_runs(tmp_base)
    assert rows[0]["status"] == "stalled"
    assert "STALLED" in rows[0]["liveness"]["detail"]
    assert rows[0]["liveness"]["silence_seconds"] > 3000


def test_a_run_whose_process_died_is_crashed_not_live_forever(tmp_base, make_run):
    """The issue's second bug: 1 candidate then a crash showed `live` forever."""
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    _age(rd, 600.0, pid=_dead_pid())
    assert runs.list_runs(tmp_base)[0]["status"] == "crashed"


def test_a_finalized_run_still_reports_done(tmp_base, make_run):
    """Degrades sanely for a finished run: no amount of silence or a departed process
    downgrades a sealed run."""
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS + [{"kind": "finalize", "test_reward": 0.9}],
                  baseline={"val": {"reward": 0.25}},
                  final={"test": {"reward": 0.9}})
    _age(rd, 86_400.0, pid=_dead_pid())
    row = runs.list_runs(tmp_base)[0]
    assert row["status"] == "done"
    assert row["liveness"]["status"] == "done"


def test_a_finalize_event_alone_is_enough_to_report_done(tmp_base, make_run):
    """A run whose log says `finalize` but whose final.json/splits.json lag must still
    read `done` — otherwise the hub says `live` while `cap-evolve tail` says `done`."""
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS + [{"t": time.time(), "kind": "finalize",
                                                  "test_reward": 0.9}],
                  baseline={"val": {"reward": 0.25}})   # no final.json, test not sealed
    row = runs.list_runs(tmp_base)[0]
    assert row["liveness"]["status"] == "done"
    assert row["status"] == "done"
    assert runs.load_run(tmp_base, "run_a")["summary"]["status"] == "done"


def test_failed_and_done_outrank_the_liveness_verdict(tmp_base, make_run):
    """Ordering: the summary-derived terminal states are decided BEFORE liveness.

    Checked on ``_status`` directly because the reducer always synthesises a ``seed``
    node, so ``counts.total == 0`` is unreachable through a real run dir — the
    ``failed`` branch predates this PR and is left exactly as it was.
    """
    from capevolve_dashboard import runs
    dead = {"status": "crashed"}
    assert runs._status({"counts": {"total": 0}}, dead) == "failed"
    assert runs._status({"counts": {"total": 0}}, {"status": "done"}) == "done"
    assert runs._status({"test_sealed": True, "counts": {"total": 3}}, dead) == "done"
    assert runs._status({"test_reward": 0.9, "counts": {"total": 3}}, dead) == "done"
    # …and only a run that is neither finished nor empty inherits the liveness verdict.
    assert runs._status({"counts": {"total": 3}}, dead) == "crashed"
    assert runs._status({"counts": {"total": 3}}, {"status": "stalled"}) == "stalled"
    assert runs._status({"counts": {"total": 3}}, {"status": "live"}) == "live"
    assert runs._status({"counts": {"total": 3}}, None) == "live"


def test_a_dead_run_with_no_candidates_is_crashed_not_live(tmp_base, make_run):
    """Previously this read `live` forever (the issue's second bug)."""
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=[{"kind": "splits", "train": 1, "val": 1, "test": 1}])
    _age(rd, 99_999.0, pid=_dead_pid())
    assert runs.list_runs(tmp_base)[0]["status"] == "crashed"


def test_a_working_run_is_live(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    assert runs.list_runs(tmp_base)[0]["status"] == "live"


def test_a_slow_but_healthy_run_is_not_reported_stalled(tmp_base, make_run):
    """THE case that must not regress: 20-minute steps, 25 minutes quiet → still live.

    The old fixed 5-minute rule called this hung, and a user's response to "hung" is to
    kill the run.
    """
    from capevolve_dashboard import runs
    slow = []
    t = time.time() - 4 * 20 * 60.0
    for ev in BASE_EVENTS:
        slow.append({**ev, "t": t})
        t += 20 * 60.0
    rd = make_run("run_a", events=slow, baseline={"val": {"reward": 0.25}})
    _age(rd, 25 * 60.0, pid=os.getpid())
    row = runs.list_runs(tmp_base)[0]
    assert row["status"] == "live", row["liveness"]
    assert row["liveness"]["stall_threshold_seconds"] > 25 * 60.0


def test_load_run_carries_the_same_verdict_as_the_hub_row(tmp_base, make_run):
    """One computation, two payloads: hub and DeepDive cannot disagree."""
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    _age(rd, 3600.0, pid=os.getpid())
    row = runs.list_runs(tmp_base)[0]
    detail = runs.load_run(tmp_base, "run_a")["summary"]
    assert detail["status"] == row["status"] == "stalled"
    assert detail["liveness"]["detail"] == row["liveness"]["detail"]


def test_liveness_never_raises_on_a_broken_run_dir(tmp_base, make_run):
    from capevolve_dashboard import runs
    rd = make_run("run_a", events=BASE_EVENTS)
    rd.events_path.write_bytes(b"\x00\xff not json at all\n")
    (rd.root / "run.pid").write_text("garbage", encoding="utf-8")
    assert runs.liveness(rd.root)["status"] in {"live", "stalled"}


# ---- SSE: a silent run gets a named verdict, not an ambiguous close --------
#
# The route is an unbounded generator, and TestClient buffers such a response instead of
# yielding frames as they are produced — so these drive the endpoint's body_iterator
# directly and stop after the frames under test. Same code path, no 5-minute wait.

def _frames(app, run_id, *, want, limit=8, **params):
    """Collect SSE frames from the live stream route until ``want`` appears in them."""
    import asyncio
    endpoint = next(r.endpoint for r in app.routes
                    if getattr(r, "path", "") == "/api/runs/{run_id}/stream")

    async def drive():
        resp = await endpoint(run_id, **params)
        out = []
        async for chunk in resp.body_iterator:
            out.append(chunk if isinstance(chunk, str) else chunk.decode())
            if want in "".join(out) or len(out) >= limit:
                break
        return "".join(out)

    return asyncio.run(drive())


def test_stream_sends_a_status_frame_naming_the_stall(tmp_base, make_run):
    from capevolve_dashboard.app import create_app

    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    _age(rd, 3600.0, pid=os.getpid())
    body = _frames(create_app(tmp_base), "run_a", want="event: status",
                   poll=0.01, status_every=0)
    assert "event: status" in body
    assert '"status": "stalled"' in body
    assert "STALLED" in body                  # the reason, with the numbers
    assert "event: idle" not in body          # the ambiguous frame is gone
    assert "event: done" not in body          # and it is NOT reported as finished


def test_stream_closes_on_crashed_but_never_calls_it_done(tmp_base, make_run):
    from capevolve_dashboard.app import create_app

    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    _age(rd, 600.0, pid=_dead_pid())
    body = _frames(create_app(tmp_base), "run_a", want="event: status",
                   poll=0.01, status_every=0)
    assert '"status": "crashed"' in body
    assert "event: done" not in body


def test_stream_status_frame_says_live_for_a_working_run(tmp_base, make_run):
    from capevolve_dashboard.app import create_app

    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})
    body = _frames(create_app(tmp_base), "run_a", want="event: status",
                   poll=0.01, status_every=0)
    assert '"status": "live"' in body
    assert "working" in body


def test_stream_still_ends_with_done_when_the_run_finalizes(tmp_base, make_run):
    """Unchanged happy path: a real finish is still a `done` frame."""
    from capevolve_dashboard.app import create_app

    rd = make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}})

    def append_finalize():
        # After the route has recorded its start offset, so the event is seen as NEW.
        time.sleep(0.3)
        with rd.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": "finalize",
                                 "test_reward": 0.9}) + "\n")

    threading.Thread(target=append_finalize, daemon=True).start()
    body = _frames(create_app(tmp_base), "run_a", want="event: done", limit=200,
                   poll=0.05, status_every=30)
    assert "event: done" in body
    assert "crashed" not in body and "stalled" not in body
