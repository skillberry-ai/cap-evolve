"""Tests for the shared events.jsonl tail helper + the --follow / tail CLI paths."""
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from cap_evolve import eventstream
from cap_evolve.cli import _cmd_tail, _events_path


def _toy_project(tmp_path: Path) -> tuple[Path, dict]:
    """Scaffold the zero-API toy_calc project (mock optimizer) + its env. Shared by the
    real end-to-end `cap-evolve run --follow` tests."""
    repo = Path(__file__).resolve().parents[2]
    example = repo / "examples" / "toy_calc"
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    shutil.copy(example / "adapter.py", proj / "adapters" / "adapter.py")
    shutil.copytree(example / "capability", tmp_path / "seed_capability")
    shutil.copy(repo / "templates" / "project" / "capevolve.yaml", proj / "capevolve.yaml")
    env = dict(os.environ)
    env.update(PYTHONPATH=str(repo / "core"), CAPEVOLVE_CORE=str(repo / "core"),
               CAPEVOLVE_SKILLS_DIR=str(repo / "skills"), CAPEVOLVE_TOY_DATA=str(example),
               CAPEVOLVE_MOCK_SCRIPT=str(example / "mock_script.json"))
    return proj, env


def _kinds(it):
    """Event kinds, minus the terminal sentinel (asserted separately)."""
    return [e["kind"] for e in it if e["kind"] != eventstream.FOLLOW_END]


def _write(p: Path, *recs):
    with p.open("a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


# ---- read_new_events -------------------------------------------------------

def test_read_new_events_incremental(tmp_path):
    p = tmp_path / "events.jsonl"
    _write(p, {"kind": "baseline", "val": 0.25})
    evs, off = eventstream.read_new_events(p, 0)
    assert evs == [{"kind": "baseline", "val": 0.25}]
    assert off == p.stat().st_size

    _write(p, {"kind": "step", "candidate": "cand_0001"})
    evs2, off2 = eventstream.read_new_events(p, off)
    assert evs2 == [{"kind": "step", "candidate": "cand_0001"}]
    assert off2 == p.stat().st_size


def test_read_new_events_leaves_partial_line(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('{"kind": "baseline"}\n{"kind": "ste', encoding="utf-8")
    evs, off = eventstream.read_new_events(p, 0)
    assert evs == [{"kind": "baseline"}]
    assert off == len('{"kind": "baseline"}\n')


def test_read_new_events_missing_file(tmp_path):
    assert eventstream.read_new_events(tmp_path / "nope.jsonl", 0) == ([], 0)


# ---- follow_events ---------------------------------------------------------

def test_follow_events_stops_on_finalize_and_replays(tmp_path):
    p = tmp_path / "events.jsonl"
    _write(p, {"kind": "baseline"}, {"kind": "finalize"}, {"kind": "after"})
    got = list(eventstream.follow_events(p, idle_timeout=1.0))
    assert _kinds(got) == ["baseline", "finalize"]  # stops at finalize, nothing after
    assert got[-1] == {"kind": eventstream.FOLLOW_END, "reason": "stop_kind",
                       "last_kind": "finalize"}


def test_follow_events_idle_timeout_on_empty(tmp_path):
    t0 = time.monotonic()
    got = list(eventstream.follow_events(tmp_path / "events.jsonl", poll=0.05, idle_timeout=0.2))
    assert _kinds(got) == []
    # #118: an idle exit is distinguishable from a finished run, not a bare return.
    assert got == [{"kind": eventstream.FOLLOW_END, "reason": "idle", "idle_seconds": 0.2}]
    assert time.monotonic() - t0 < 5.0


def test_follow_events_picks_up_appends_live(tmp_path):
    p = tmp_path / "events.jsonl"
    _write(p, {"kind": "baseline"})

    def writer():
        time.sleep(0.15)
        _write(p, {"kind": "step", "accept": True})
        time.sleep(0.15)
        _write(p, {"kind": "finalize"})

    threading.Thread(target=writer, daemon=True).start()
    kinds = _kinds(eventstream.follow_events(p, poll=0.05, idle_timeout=5.0))
    assert kinds == ["baseline", "step", "finalize"]


def test_follow_events_should_stop_drains_tail(tmp_path):
    """A stop signal must not lose events written just before it."""
    p = tmp_path / "events.jsonl"
    stop = threading.Event()
    _write(p, {"kind": "baseline"}, {"kind": "step"})
    stop.set()  # already stopped: first read yields both, then the drain returns
    got = list(eventstream.follow_events(
        p, poll=0.01, idle_timeout=1.0, should_stop=lambda _last: stop.is_set()))
    assert _kinds(got) == ["baseline", "step"]
    assert got[-1]["reason"] == "should_stop"


# ---- format_event / render_line --------------------------------------------

def test_format_event_covers_the_key_kinds():
    assert "splits frozen" in eventstream.format_event(
        {"kind": "splits", "train": 4, "val": 2, "test": 2})
    assert "baseline  val=0.2500" in eventstream.format_event({"kind": "baseline", "val": 0.25})
    acc = eventstream.format_event(
        {"kind": "step", "candidate": "cand_0001", "accept": True, "val": 1.0,
         "parent_val": 0.0, "reason": "Δ>0"})
    assert "ACCEPT" in acc and "cand_0001" in acc and "Δ>0" in acc
    rej = eventstream.format_event({"kind": "step", "candidate": "c2", "accept": False, "val": 0.5})
    assert "reject" in rej
    fin = eventstream.format_event(
        {"kind": "finalize", "test_reward": 1.0, "test_baseline_reward": 0.0,
         "test_delta": 1.0, "best_id": "cand_0001"})
    assert "FINALIZE" in fin and "test=1.0000" in fin
    assert "BUDGET 80%" in eventstream.format_event(
        {"kind": "budget_warning", "pct": 80, "metric": "max_usd", "spent": 8, "limit": 10})
    assert "OPTIMIZER ERROR" in eventstream.format_event(
        {"kind": "optimizer_error", "candidate": "c1", "error": "boom"})


def test_format_event_skips_bookkeeping_kinds():
    assert eventstream.format_event({"kind": "minibatch", "tag": "mb"}) is None
    assert eventstream.format_event({"kind": "optimizer_context_warning"}) is None


def test_format_event_shows_unknown_kinds():
    line = eventstream.format_event({"kind": "brand_new_thing", "x": 1})
    assert "brand_new_thing" in line and "x=1" in line


def test_cost_meter_accumulates_across_events():
    """Runner spend comes from `evaluate`, optimizer spend from `step` — once each."""
    totals = {}
    eventstream.format_event({"kind": "evaluate", "cost_usd": 0.01, "tokens": 500}, totals)
    line = eventstream.format_event(
        {"kind": "step", "cost_usd": 0.01, "tokens": 500,          # re-stated, must NOT recount
         "opt_cost_usd": 0.02, "opt_tokens": 1500}, totals)
    assert abs(totals["usd"] - 0.03) < 1e-9 and totals["tokens"] == 2000
    assert "$0.0300" in line and "2.0k tok" in line


def test_format_event_never_emits_ansi():
    """format_event is pure text; only render_line(color=True) adds escapes."""
    for ev in ({"kind": "step", "accept": True, "candidate": "c"},
               {"kind": "optimizer_error", "candidate": "c", "error": "x"},
               {"kind": "finalize", "test_reward": 1.0}):
        assert "\033" not in eventstream.format_event(ev)


def test_render_line_color_on_and_off():
    ev = {"kind": "step", "accept": True, "candidate": "c", "val": 1.0}
    assert "\033[32m" in eventstream.render_line(ev, color=True)
    assert "\033" not in eventstream.render_line(ev, color=False)


def test_use_color_false_for_non_tty_and_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert eventstream.use_color(io.StringIO()) is False        # not a tty
    assert eventstream.use_color(object()) is False             # no isatty attr

    class Tty(io.StringIO):
        def isatty(self):
            return True
    assert eventstream.use_color(Tty()) is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert eventstream.use_color(Tty()) is False


# ---- CLI: tail -------------------------------------------------------------

def test_events_path_prefers_run_ts_and_ignores_pre_existing(tmp_path):
    (tmp_path / "run_old").mkdir()
    (tmp_path / "run_new").mkdir()
    assert _events_path(tmp_path, "old", None) == tmp_path / "run_old" / "events.jsonl"
    # unpinned: skip the dirs that existed before this run started
    assert _events_path(tmp_path, None, {"run_old"}) == tmp_path / "run_new" / "events.jsonl"
    assert _events_path(tmp_path, None, {"run_old", "run_new"}) is None


def test_cmd_tail_missing_base(tmp_path, capsys):
    assert _cmd_tail(["--base", str(tmp_path)]) == 1
    assert "no run_* dirs" in capsys.readouterr().err


def test_cmd_tail_from_start_plain_when_piped(tmp_path, capsys):
    """capsys stdout is not a TTY → plain lines, no ANSI (the CI/piped case)."""
    root = tmp_path / "run_x"
    root.mkdir()
    _write(root / "events.jsonl",
           {"kind": "baseline", "val": 0.0},
           {"kind": "step", "candidate": "cand_0001", "accept": True, "val": 1.0,
            "parent_val": 0.0},
           {"kind": "finalize", "test_reward": 1.0, "test_baseline_reward": 0.0,
            "test_delta": 1.0, "best_id": "cand_0001"})
    assert _cmd_tail([str(root), "--from-start"]) == 0
    out = capsys.readouterr().out
    assert "\033" not in out
    assert "baseline" in out and "ACCEPT" in out and "FINALIZE" in out


def test_cmd_tail_attaches_to_an_ongoing_run(tmp_path, capsys):
    """Default (no --from-start) skips history and follows new events only."""
    root = tmp_path / "run_x"
    root.mkdir()
    ev = root / "events.jsonl"
    _write(ev, {"kind": "baseline", "val": 0.0})  # history: must NOT be printed

    def writer():
        time.sleep(0.2)
        _write(ev, {"kind": "step", "candidate": "cand_0007", "accept": True, "val": 1.0})
        _write(ev, {"kind": "finalize", "test_reward": 1.0})

    threading.Thread(target=writer, daemon=True).start()
    assert _cmd_tail([str(root), "--idle-timeout", "10"]) == 0
    out = capsys.readouterr().out
    assert "cand_0007" in out and "FINALIZE" in out
    assert "val=0.0000 ±" not in out  # the pre-attach baseline line was skipped


def test_tail_is_a_registered_subcommand():
    out = subprocess.run([sys.executable, "-m", "cap_evolve.cli"],
                         capture_output=True, text=True).stderr
    assert "tail" in out


def test_run_follow_end_to_end_pipes_clean_progress(tmp_path):
    """Real `cap-evolve run --follow` over toy_calc (zero API, mock optimizer).

    stdout is piped (not a TTY), so: progress lines land on stderr with NO ANSI, and
    stdout stays the parseable final JSON that scripts depend on.
    """
    proj, env = _toy_project(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run", "--spec", str(proj / "capevolve.yaml"),
         "--project", str(proj), "--run-ts", "t", "--follow", "--dashboard", "off"],
        capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]

    # progress went to stderr, live, and is plain text (safe for CI logs)
    assert "\033" not in proc.stderr, "ANSI leaked into non-TTY output"
    assert "splits frozen" in proc.stderr
    assert "baseline  val=" in proc.stderr
    assert "ACCEPT" in proc.stderr, proc.stderr          # >=1 per-candidate line
    assert "FINALIZE" in proc.stderr                     # the finalize line
    # stdout is still just the final JSON blob
    assert json.loads(proc.stdout)["test_reward"] == 1.0


def test_dashboard_stream_reexports_the_shared_helper():
    """The SSE route and the CLI must read events.jsonl through the same function."""
    root = Path(__file__).resolve().parents[2] / "dashboard" / "backend"
    sys.path.insert(0, str(root))
    try:
        from capevolve_dashboard import stream
        assert stream.read_new_events is eventstream.read_new_events
    finally:
        sys.path.remove(str(root))


# ---- B1: a malformed record must never kill the follower --------------------

POISON = [
    {"kind": "baseline", "t": "not-a-number"},   # ValueError from float()
    {"kind": "baseline", "t": {"nested": 1}},    # TypeError from float()
    {"kind": "baseline", "t": 1e300},            # OverflowError from localtime()
    42, None, [1, 2, 3], "just a string",        # non-dict records
]


def test_format_event_survives_every_malformed_record():
    """format_event is total: no record shape may raise out of the render loop."""
    for bad in POISON:
        line = eventstream.format_event(bad, {})          # must not raise
        assert line is None or isinstance(line, str)
    assert "--:--:--" in eventstream.format_event({"kind": "baseline", "t": "nope"})
    assert eventstream.format_event(42) is None


def test_poisoned_record_does_not_kill_the_follower(tmp_path):
    """The bug #116 exists to fix: one bad event must not blank the rest of the run."""
    p = tmp_path / "events.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "baseline", "val": 0.1}) + "\n")
        fh.write(json.dumps({"kind": "baseline", "t": "not-a-number"}) + "\n")
        fh.write("42\n")                    # non-dict record
        fh.write("NOT JSON AT ALL\n")       # unparseable
        fh.write(json.dumps({"kind": "step", "candidate": "cand_0001", "accept": True,
                             "val": 1.0}) + "\n")
        fh.write(json.dumps({"kind": "finalize", "test_reward": 1.0}) + "\n")
    lines = [eventstream.render_line(e, {})
             for e in eventstream.follow_events(p, idle_timeout=2.0)]
    text = "\n".join(l for l in lines if l)
    assert "cand_0001" in text and "FINALIZE" in text   # events AFTER the poison render
    assert "--:--:--" in text                           # the poisoned one degraded, not fatal


def test_follower_thread_reports_instead_of_dying_silently(tmp_path, monkeypatch, capsys):
    """If the follower does die, the user is TOLD — silence must never look like progress."""
    from cap_evolve import cli as _cli

    base = tmp_path
    (base / "run_z").mkdir()
    _write(base / "run_z" / "events.jsonl", {"kind": "baseline", "val": 0.0})
    boom = RuntimeError("simulated renderer explosion")
    monkeypatch.setattr(eventstream, "render_line",
                        lambda *a, **k: (_ for _ in ()).throw(boom))
    monkeypatch.setattr(_cli, "_stderr_is_usable", lambda: True)
    stop, t = _cli._spawn_follower(base, "z", None)
    t.join(timeout=5.0)
    assert not t.is_alive()
    assert "[follow] live progress stopped" in capsys.readouterr().err


# ---- B1b/N2: only dict records escape read_new_events -----------------------

def test_read_new_events_filters_non_dict_records(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('42\nnull\n[1,2]\n"str"\ntrue\n{"kind":"finalize"}\n', encoding="utf-8")
    evs, _ = eventstream.read_new_events(p, 0)
    assert [e["kind"] for e in evs if e["kind"] != "log_corruption"] == ["finalize"]
    assert all(isinstance(e, dict) for e in evs)
    assert {"kind": "log_corruption", "dropped": 5} in evs   # damage is reported, not hidden


def test_corrupt_line_is_counted_not_silently_dropped(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('{"kind":"a"}\nNOT JSON AT ALL\n{"kind":"finalize"}\n', encoding="utf-8")
    evs, _ = eventstream.read_new_events(p, 0)
    assert [e["kind"] for e in evs] == ["a", "finalize", "log_corruption"]
    assert "1 unreadable record" in eventstream.format_event(evs[-1])


# ---- N3: a shrunk file re-reads instead of getting stuck --------------------

def test_read_new_events_rereads_after_truncation(tmp_path):
    p = tmp_path / "events.jsonl"
    _write(p, {"kind": "a"}, {"kind": "b"})
    _, off = eventstream.read_new_events(p, 0)
    p.write_text('{"kind":"x"}\n', encoding="utf-8")       # rewritten shorter
    evs, off2 = eventstream.read_new_events(p, off)
    assert [e["kind"] for e in evs] == ["x"] and off2 == p.stat().st_size


# ---- B2: terminal escape injection -----------------------------------------

def test_escape_injection_from_event_payloads_is_neutralised():
    """All three demonstrated attacks: OSC title, screen clear, newline-forged line."""
    osc = eventstream.format_event({"kind": "optimizer_error", "candidate": "c1",
                                   "error": "boom\033]0;PWNED\007\033[2J\033[31mfake red"})
    clear = eventstream.format_event({"kind": "brand_new", "payload": "\033[2J\033[Hcleared"})
    forge = eventstream.format_event(
        {"kind": "brand_new",
         "payload": "a\nFINALIZE  test=1.0000 (baseline 0.0000) best=FAKE"})
    for line in (osc, clear, forge):
        assert "\033" not in line and "\x1b" not in line
        assert "\007" not in line and "\x9b" not in line
        assert "\n" not in line and "\r" not in line       # cannot forge extra lines
        assert line.count("\n") == 0 and len(line.splitlines()) == 1
    assert "PWNED" in osc and "boom" in osc                # inert, but still readable
    assert "⏎" in forge and "FINALIZE" in forge            # visibly one line, not two


def test_sanitize_strips_c0_c1_and_keeps_tab():
    # ESC/BEL/DEL and 8-bit CSI vanish; the leftover "[31m" is inert printable text.
    assert eventstream.sanitize("a\x1b[31mb\x07c\x9bd\x7fe") == "a[31mbcde"
    assert eventstream.sanitize("\x1b]0;t\x07\x1b[2J\x1b[H") == "]0;t[2J[H"
    assert eventstream.sanitize("a\tb") == "a\tb"
    assert eventstream.sanitize("a\nb\rc") == "a⏎b⏎c"


def test_render_line_is_also_escape_safe_with_color():
    """color=True adds exactly the styling escapes — never the payload's own."""
    ev = {"kind": "optimizer_error", "candidate": "c", "error": "x\033]0;PWNED\007"}
    line = eventstream.render_line(ev, color=True)
    assert line.startswith("\033[31m") and line.endswith("\033[0m")
    assert "\033" not in line[5:-4] and "PWNED" in line


# ---- B3: the cost meter must equal the run's own recorded total -------------

def test_cost_meter_matches_the_runs_recorded_total(tmp_path):
    """The meter must equal Spent.total_usd, not double-count the runner."""
    from cap_evolve.rundir import RunDir

    rd = RunDir.create(tmp_path, ts="cost")
    # Exactly what the harness does: evaluate logs runner spend (harness.py:307-312),
    # then step re-states it alongside the optimizer's own (harness.py:1322-1328).
    rd.update_spent(metric_calls=2, usd=0.50, runner_tokens=1000)
    rd.log_event("evaluate", split="val", tag="cand_0001", reward=1.0,
                 cost_usd=0.50, tokens=1000, seconds=1.0)
    rd.update_spent(optimizer_seconds=1.0, optimizer_usd=0.20, optimizer_tokens=500)
    rd.log_event("step", candidate="cand_0001", accept=True, val=1.0, parent_val=0.0,
                 cost_usd=0.50, tokens=1000, opt_cost_usd=0.20, opt_tokens=500)

    totals: dict = {}
    events, _ = eventstream.read_new_events(rd.events_path, 0)
    for ev in events:
        eventstream.format_event(ev, totals)
    recorded = rd.spent.total_usd
    assert abs(recorded - 0.70) < 1e-9, recorded
    assert abs(totals["usd"] - recorded) < 1e-9, (totals, recorded)
    assert totals["tokens"] == 1500


def test_accrue_totals_is_public_for_138():
    assert eventstream.accrue_totals in vars(eventstream).values()
    assert "accrue_totals" in eventstream.__all__
    t: dict = {}
    eventstream.accrue_totals({"kind": "intake", "usd": 0.05, "tokens": 100}, t)
    eventstream.accrue_totals({"kind": "gepa_local_gate", "cost_usd": 99.0}, t)  # not a cost event
    assert t == {"usd": 0.05, "tokens": 100}


# ---- B4: closed stderr must not corrupt the stdout JSON contract ------------

def test_stderr_unusable_disables_following(monkeypatch):
    from cap_evolve import cli as _cli

    monkeypatch.setattr(sys, "stderr", None)
    assert _cli._stderr_is_usable() is False
    assert _cli._spawn_follower(Path("/nope"), "x", None) == (None, None)

    class Reused(io.StringIO):
        def fileno(self):
            return 7            # fd 2 was closed and handed to another file
    monkeypatch.setattr(sys, "stderr", Reused())
    assert _cli._stderr_is_usable() is False


def test_run_follow_with_stderr_closed_keeps_stdout_valid_json(tmp_path):
    """`cap-evolve run --follow 2>&-` must still emit parseable JSON on stdout."""
    proj, env = _toy_project(tmp_path)
    out = tmp_path / "cl.out"
    # Real `2>&-`: the shell closes fd 2 before exec, so CPython starts with a dead
    # stderr and would hand fd 2 to the next open() — the corruption path.
    cmd = (f"exec 2>&-; {shlex.quote(sys.executable)} -m cap_evolve.cli run "
           f"--spec {shlex.quote(str(proj / 'capevolve.yaml'))} "
           f"--project {shlex.quote(str(proj))} --run-ts cl --follow --dashboard off "
           f"> {shlex.quote(str(out))}")
    proc = subprocess.run(["/bin/sh", "-c", cmd], env=env, timeout=600)
    assert proc.returncode == 0
    text = out.read_text()
    assert json.loads(text)["test_reward"] == 1.0          # contract intact
    assert "baseline  val=" not in text                    # no progress leaked into stdout


# ---- N1: tail exit codes ----------------------------------------------------

def test_cmd_tail_rejects_a_path_that_can_never_be_a_run_dir(tmp_path, capsys):
    assert _cmd_tail([str(tmp_path / "no" / "such" / "run_typo")]) == 2
    assert "no such run dir" in capsys.readouterr().err


def test_cmd_tail_returns_3_on_idle_timeout_with_no_events(tmp_path, capsys):
    assert _cmd_tail([str(tmp_path / "run_pending"), "--idle-timeout", "0.2"]) == 3
    assert "timed out" in capsys.readouterr().err


def test_cmd_tail_rejects_negative_idle_timeout(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        _cmd_tail([str(tmp_path), "--idle-timeout", "-5"])


# ---- #138: every kind is reachable -----------------------------------------

def test_skip_kinds_can_be_disabled_to_see_bookkeeping_events():
    ev = {"kind": "minibatch", "tag": "mb1"}
    assert eventstream.format_event(ev) is None                       # default: hidden
    assert "minibatch" in eventstream.format_event(ev, skip_kinds=())  # #138: visible
    assert "minibatch" in eventstream.render_line(ev, skip_kinds=())
    assert eventstream.BOOKKEEPING_KINDS                              # documented set
