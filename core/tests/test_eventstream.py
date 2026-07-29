"""Tests for the shared events.jsonl tail helper + the --follow / tail CLI paths."""
import io
import os
import shutil
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from cap_evolve import eventstream
from cap_evolve.cli import _cmd_tail, _events_path


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
    kinds = [e["kind"] for e in eventstream.follow_events(p, idle_timeout=1.0)]
    assert kinds == ["baseline", "finalize"]  # stops at finalize, nothing after


def test_follow_events_idle_timeout_on_empty(tmp_path):
    t0 = time.monotonic()
    got = list(eventstream.follow_events(tmp_path / "events.jsonl", poll=0.05, idle_timeout=0.2))
    assert got == []
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
    kinds = [e["kind"] for e in eventstream.follow_events(p, poll=0.05, idle_timeout=5.0)]
    assert kinds == ["baseline", "step", "finalize"]


def test_follow_events_should_stop_drains_tail(tmp_path):
    """A stop signal must not lose events written just before it."""
    p = tmp_path / "events.jsonl"
    stop = threading.Event()
    _write(p, {"kind": "baseline"}, {"kind": "step"})
    stop.set()  # already stopped: first read yields both, then the drain returns
    kinds = [e["kind"] for e in eventstream.follow_events(
        p, poll=0.01, idle_timeout=1.0, should_stop=stop.is_set)]
    assert kinds == ["baseline", "step"]


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
    totals = {}
    eventstream.format_event({"kind": "step", "cost_usd": 0.01, "tokens": 500}, totals)
    line = eventstream.format_event({"kind": "step", "cost_usd": 0.02, "tokens": 1500}, totals)
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
