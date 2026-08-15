"""``cap-evolve replay`` — the recorded demo session feeds the SAME reducer +
renderer the live view uses, and the bundled sample stays honest about being synthetic.
"""

import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

#: What the committed demo session claims. If the generator changes these, the numbers
#: quoted in docs/tests change with it — deliberately load-bearing.
DEMO_BEST_VAL = 0.8333
DEMO_BEST_ID = "cand_0007"
DEMO_TEST = 0.8333333333333333


class _Plain(io.StringIO):
    def isatty(self):
        return False


def _demo_events():
    from cap_evolve import tui
    return [json.loads(ln) for ln in
            (tui.DEMO_DIR / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()]


# ---- the bundled session ----------------------------------------------------

def test_demo_session_is_shipped_and_parseable():
    from cap_evolve import tui
    assert (tui.DEMO_DIR / "events.jsonl").exists()
    assert (tui.DEMO_DIR / "baseline.json").exists()
    assert (tui.DEMO_DIR / "final.json").exists()
    kinds = [e.get("kind") for e in _demo_events()]
    # a realistic pipeline: splits → baseline → a mix of verdicts → gate warning → finalize
    for expected in ("splits", "baseline", "step", "step_indecisive",
                     "gate_warning", "optimizer_error", "finalize"):
        assert expected in kinds, expected
    steps = [e for e in _demo_events() if e.get("kind") == "step"]
    assert any(e["accept"] for e in steps) and any(not e["accept"] for e in steps)


def test_demo_session_events_render_through_the_real_event_stream():
    """The recording can't drift from what the renderer consumes."""
    from cap_evolve import eventstream
    for e in _demo_events():
        line = eventstream.format_event(e, {})
        assert line is None or "\x1b" not in line


def test_demo_session_is_byte_stable_on_regeneration():
    """A fixed base timestamp, not time.time() — so the committed file is reproducible."""
    from cap_evolve import tui
    before = (tui.DEMO_DIR / "events.jsonl").read_bytes()
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "generate_demo_session.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tui.DEMO_DIR / "events.jsonl").read_bytes() == before


def test_demo_banner_says_it_is_not_a_benchmark():
    """HONESTY: synthetic numbers must never be presentable as a benchmark result."""
    from cap_evolve import tui
    banner = tui.DEMO_BANNER.lower()
    assert "sample" in banner or "illustrative" in banner
    assert "synthetic" in banner
    assert "no benchmark claim" in banner
    # ...and the statement travels with the data, not just the CLI.
    head = (tui.DEMO_DIR / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert "benchmark" in head.lower() and "sample" in head.lower()
    gen = (REPO / "scripts" / "generate_demo_session.py").read_text(encoding="utf-8")
    assert "ILLUSTRATIVE SAMPLE" in gen


# ---- replay through the real renderer --------------------------------------

def test_replay_demo_completes_and_final_frame_shows_the_best_value():
    from cap_evolve import tui
    buf = _Plain()
    tui.replay(tui.DEMO_DIR, stream=buf, color=False, speed=10_000.0, max_gap=0.0,
               banner=tui.DEMO_BANNER)
    out = buf.getvalue()
    assert tui.DEMO_BANNER in out
    # the final frame is the last thing written before the closing banner
    assert f"best↑ {DEMO_BEST_VAL:.3f}" in out
    assert DEMO_BEST_ID in out
    assert f"test (sealed) {DEMO_TEST:.3f}" in out
    assert "FINALIZE" in out


def test_replay_demo_piped_is_ansi_free():
    from cap_evolve import tui
    buf = _Plain()
    tui.replay(tui.DEMO_DIR, stream=buf, color=False, speed=10_000.0, max_gap=0.0)
    assert not _ANSI.search(buf.getvalue()), _ANSI.search(buf.getvalue()).group()


def test_replay_only_reveals_the_test_result_once_finalize_arrives():
    """The frame must never show a number the log has not reached yet."""
    from cap_evolve import tui
    buf = _Plain()
    tui.replay(tui.DEMO_DIR, stream=buf, color=False, speed=10_000.0, max_gap=0.0)
    out = buf.getvalue()
    assert out.index("FINALIZE") < out.index("test (sealed)")


def test_replay_of_a_recorded_run_dir_matches_a_direct_reduce():
    """Replay is the same projection as the live view, not a parallel mock."""
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "run_x"
        root.mkdir()
        (root / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in _demo_events()), encoding="utf-8")
        for name in ("baseline.json", "final.json"):
            (root / name).write_bytes((tui.DEMO_DIR / name).read_bytes())
        s = tui._reduce(root)["summary"]
        assert s["best_id"] == DEMO_BEST_ID
        assert abs(s["best_val"] - DEMO_BEST_VAL) < 1e-9
        assert abs(s["test_reward"] - DEMO_TEST) < 1e-9


# ---- the CLI surface --------------------------------------------------------

def _cli(*argv):
    from cap_evolve import cli
    return cli.main(list(argv))


def test_cli_registers_watch_and_replay():
    from cap_evolve import cli
    assert "watch" in cli.COMMANDS and "replay" in cli.COMMANDS


def test_cli_replay_rejects_ambiguous_source():
    try:
        _cli("replay", "--demo", "some/dir")
    except SystemExit as e:      # argparse error path
        assert e.code == 2
    else:
        raise AssertionError("expected argparse to reject demo + run_dir")


def test_cli_replay_missing_run_dir_is_exit_2():
    with tempfile.TemporaryDirectory() as d:
        assert _cli("replay", str(Path(d) / "nope")) == 2


def test_cli_watch_with_no_runs_is_exit_1():
    with tempfile.TemporaryDirectory() as d:
        assert _cli("watch", "--base", d) == 1


def test_cli_watch_named_dir_that_can_never_exist_is_exit_2():
    assert _cli("watch", "/nonexistent-parent-xyz/run_1") == 2


def test_cli_replay_demo_end_to_end_is_ansi_free_when_piped():
    """The real entry point, in a subprocess, with stderr captured (not a TTY)."""
    # The console script's own entry point (cap_evolve.cli:main), not `python -m
    # cap_evolve` — that module is a deliberately smaller host-agnostic surface.
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; from cap_evolve.cli import main; sys.exit(main(sys.argv[1:]))",
         "replay", "--demo", "--speed", "10000", "--no-color"],
        capture_output=True, text=True, cwd=str(REPO), timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(CORE)})
    assert r.returncode == 0, r.stderr[-2000:]
    assert not _ANSI.search(r.stderr), _ANSI.search(r.stderr).group()
    assert "no benchmark claim" in r.stderr
    assert f"best↑ {DEMO_BEST_VAL:.3f}" in r.stderr
    assert r.stdout == "", r.stdout   # stdout stays clean for machine consumers
