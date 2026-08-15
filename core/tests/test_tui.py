"""The live TUI: the height budget never overflows, the renderer is pure and total,
and no event value can reach the terminal as an escape sequence.

The renderer is a pure function of one reduced run, so every assertion here runs
without a TTY, a run in flight, or an optimizer.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

_EVENTS = [
    {"t": 1772445600.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"t": 1772445601.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
     "stderr": 0.1, "cost_usd": 0.01, "tokens": 100, "seconds": 1.0},
    {"t": 1772445602.0, "kind": "baseline", "val": 0.25, "stderr": 0.1},
    {"t": 1772445603.0, "kind": "step", "candidate": "cand_0001", "accept": True,
     "reason": "up", "val": 0.75, "parent": "seed", "parent_val": 0.25,
     "optimizer_seconds": 1.2, "runner_seconds": 0.5, "cost_usd": 0.01, "tokens": 500,
     "opt_cost_usd": 0.2, "opt_tokens": 2000},
    {"t": 1772445604.0, "kind": "step", "candidate": "cand_0002", "accept": False,
     "reason": "indecisive: within noise", "val": 0.7, "parent": "cand_0001",
     "parent_val": 0.75, "optimizer_seconds": 1.0, "runner_seconds": 0.4},
]
_BASELINE = {"val": {"reward": 0.25, "per_task": [{"task_id": "t1", "reward": 0.0},
                                                  {"task_id": "t2", "reward": 0.5}]}}


def _mk_run(tmp: Path, *, events=_EVENTS, baseline=_BASELINE, final=None) -> Path:
    root = Path(tmp) / "run_demo"
    root.mkdir(parents=True, exist_ok=True)
    (root / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    if baseline is not None:
        (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if final is not None:
        (root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    return root


def _reduced(tmp: Path, **kw):
    from cap_evolve import tui
    return tui._reduce(_mk_run(tmp, **kw))


# ---- the height budget ------------------------------------------------------

def test_plan_section_sizes_never_exceeds_budget():
    """The invariant that stops an inline repaint from duplicating frames."""
    from cap_evolve.tui import plan_section_sizes
    for rows in list(range(0, 121)) + [200, 500]:
        for chart in (True, False):
            for tree in (True, False):
                for act in (True, False):
                    for tr in (None, 0, 1, 3, 99):
                        s = plan_section_sizes(rows, has_chart=chart, has_tree=tree,
                                               has_activity=act, tree_rows=tr)
                        assert all(v >= 0 for v in s.values()), (rows, s)
                        assert sum(s.values()) <= rows, (rows, s)


def test_plan_section_sizes_tiny_terminals_keep_the_header_first():
    from cap_evolve.tui import plan_section_sizes
    for rows in range(1, 21):
        s = plan_section_sizes(rows)
        assert s["header"] >= 1, (rows, s)
        assert sum(s.values()) <= rows
    # A 1-row terminal has room for nothing but one header row.
    assert plan_section_sizes(1) == {"header": 1, "footer": 0, "tree": 0,
                                     "activity": 0, "chart": 0}
    # Sections that never got their minimum stay at zero rather than being resurrected
    # by the growth pass.
    assert plan_section_sizes(4)["chart"] == 0


def test_plan_section_sizes_disabled_sections_get_nothing():
    from cap_evolve.tui import plan_section_sizes
    s = plan_section_sizes(40, has_chart=False, has_activity=False)
    assert s["chart"] == 0 and s["activity"] == 0
    assert sum(s.values()) <= 40


# ---- render_frame: pure, total, height-respecting ---------------------------

def test_render_frame_never_taller_than_the_terminal():
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d))
        for rows in list(range(1, 60)) + [200]:
            frame = tui.render_frame(r, (100, rows))
            assert frame.count("\n") + 1 <= rows, rows


def test_render_frame_is_pure():
    """Two calls with the same inputs give the same bytes, and the input is untouched."""
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d))
        snapshot = json.dumps(r, sort_keys=True, default=str)
        a = tui.render_frame(r, (90, 30), elapsed=12.0)
        b = tui.render_frame(r, (90, 30), elapsed=12.0)
        assert a == b
        assert json.dumps(r, sort_keys=True, default=str) == snapshot


def test_render_frame_shows_the_run_state():
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d), final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        out = tui.render_frame(r, (120, 40), root="/tmp/run_demo")
        assert "cap-evolve" in out
        assert "cand_0001" in out and "cand_0002" in out
        assert "0.750" in out                        # best val
        assert "base 0.250" in out                   # baseline
        assert "optimize" in out and "finalize" in out   # phase breadcrumb
        assert "★" in out                            # best marker
        assert "~" in out                            # the indecisive step
        assert "/tmp/run_demo" in out                # footer
        assert "Ctrl-C to detach" in out


def test_render_frame_survives_malformed_and_truncated_input():
    """A renderer that raises silences the run — so it must never raise."""
    from cap_evolve import tui
    bad = [
        {}, {"graph": None, "summary": None}, {"summary": {}},
        {"graph": {"nodes": [None, 42, "x"]}, "summary": {}},
        {"graph": {"nodes": [{"id": "a", "parent": "a"}], "root": "a"}, "summary": {}},
        {"graph": {"nodes": [{"id": "a", "parent": "b"}], "root": "zz"},
         "summary": {"counts": "nope", "cost": None, "budget": 7}},
        {"graph": {"nodes": [{"id": "x", "iteration": 1, "best_so_far": "NaN-ish",
                              "val": None, "parent_val": "?"}]},
         "summary": {"best_val": "x", "baseline_val": None, "tokens": "many"}},
    ]
    for r in bad:
        for size in ((80, 24), (20, 1), (1, 1), (200, 3)):
            out = tui.render_frame(r, size)
            assert isinstance(out, str)
            assert out.count("\n") + 1 <= max(1, size[1])
    # A cycle in the lineage must terminate, not hang or recurse forever.
    cyc = {"graph": {"nodes": [{"id": "a", "parent": "b"}, {"id": "b", "parent": "a"}],
                     "root": "a"}, "summary": {}}
    assert "a" in tui.render_frame(cyc, (80, 30))


def test_render_frame_truncated_events_file():
    """A half-written events.jsonl (crash mid-append) still renders."""
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        root = _mk_run(Path(d))
        text = (root / "events.jsonl").read_text(encoding="utf-8")
        (root / "events.jsonl").write_text(text[: len(text) - 40], encoding="utf-8")
        assert tui.render_frame(tui._reduce(root), (100, 30))


# ---- terminal safety --------------------------------------------------------

def test_escape_sequence_smuggled_through_an_event_is_stripped():
    """An ESC/OSC payload in a model-controlled field must never reach the terminal."""
    from cap_evolve import tui
    hostile = "\x1b]0;pwned\x07\x1b[2J\x1b[31mBOOM\r\nFINALIZE test=1.0"
    events = _EVENTS + [
        {"t": 1772445605.0, "kind": "step", "candidate": "cand_evil\x1b[5m",
         "accept": False, "reason": hostile, "val": 0.1, "parent": "seed",
         "parent_val": 0.25},
    ]
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d), events=events)
        out = tui.render_frame(r, (400, 60), color=False)
        assert "\x1b" not in out
        assert "\x07" not in out and "\r" not in out
        assert "BOOM" in out            # stripped of control chars, not of content
        assert "pwned" in out
        # colored output carries ONLY the palette's own codes, never the payload's
        colored = tui.render_frame(r, (400, 60), color=True)
        assert "\x1b]0;" not in colored and "\x1b[2J" not in colored
        assert "\x1b[5m" not in colored


def test_non_tty_output_has_no_ansi():
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d))
        out = tui.render_frame(r, (100, 40), color=False)
        assert not _ANSI.search(out), _ANSI.search(out)
    assert not _ANSI.search(tui.render_frame({}, (100, 40), color=False))


def test_watch_on_a_non_tty_falls_back_to_line_output():
    """No cursor moves, no frames — just the existing line-oriented stream."""
    import io

    from cap_evolve import tui

    class _Plain(io.StringIO):
        def isatty(self):
            return False

    with tempfile.TemporaryDirectory() as d:
        root = _mk_run(Path(d), events=_EVENTS + [
            {"t": 1772445606.0, "kind": "finalize", "test_reward": 0.8,
             "test_baseline_reward": 0.25, "test_delta": 0.55, "best_id": "cand_0001"}])
        buf = _Plain()
        tui.watch(root, stream=buf, color=False, idle_timeout=1.0)
        out = buf.getvalue()
        assert "baseline" in out and "FINALIZE" in out
        assert not _ANSI.search(out)
        assert "\x1b[" not in out       # no cursor-up repaint on a pipe


# ---- helpers ----------------------------------------------------------------

def test_small_formatters():
    from cap_evolve.tui import _fmt_dur, _fmt_tokens, _sparkline, _spinner
    assert _fmt_tokens(0) == "0" and _fmt_tokens(1234) == "1.2k"
    assert _fmt_tokens(3_400_000) == "3.4M" and _fmt_tokens(None) == "0"
    assert _fmt_dur(43) == "43s" and _fmt_dur(423) == "7m03s" and _fmt_dur(3723) == "1h02m03s"
    assert _fmt_dur("junk") == "—"
    assert _sparkline([]) == "" and len(_sparkline([1, 2, 3])) == 3
    assert _sparkline([0, 1])[0] == "▁" and _sparkline([0, 1])[-1] == "█"
    assert _sparkline([1, 1, 1]) == "▁▁▁"        # flat series must not divide by zero
    assert _sparkline([None, "x", 5]) == "▁"     # non-numbers dropped, never raise
    assert len(_spinner()) == 1
