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
    one = plan_section_sizes(1)
    assert one["header"] == 1
    assert all(v == 0 for k, v in one.items() if k != "header"), one
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


# ---- the height budget with the new panels ---------------------------------

def test_plan_section_sizes_sweep_with_every_panel_combination():
    """~4000 combinations: the sum-never-exceeds invariant must hold for all of them."""
    from cap_evolve.tui import plan_section_sizes
    for rows in list(range(0, 61)) + [80, 120, 200, 500]:
        for algo in (True, False):
            for heat in (True, False):
                for dif in (True, False):
                    for caps in (None, 0, 1, 4, 99):
                        s = plan_section_sizes(rows, has_algo=algo, has_heatmap=heat,
                                               has_diff=dif, tree_rows=caps,
                                               heatmap_rows=caps, diff_rows=caps,
                                               header_rows=caps)
                        assert all(v >= 0 for v in s.values()), (rows, s)
                        assert sum(s.values()) <= rows, (rows, s)


def test_disabled_new_panels_get_no_rows():
    from cap_evolve.tui import plan_section_sizes
    s = plan_section_sizes(60)
    assert s["algo"] == 0 and s["heatmap"] == 0 and s["diff"] == 0


def test_render_frame_height_holds_with_the_new_panels():
    from cap_evolve import tui
    diff = {"title": "a → b", "lines": [f"  + line {i}" for i in range(40)]}
    stats = {"kinds": {"gepa_select": 2, "gepa_local_gate": 3}, "mb_pass": 2, "mb_fail": 1}
    with tempfile.TemporaryDirectory() as d:
        r = _reduced(Path(d))
        for cols in (20, 40, 80, 100, 200):
            for rows in list(range(1, 60)) + [200]:
                frame = tui.render_frame(r, (cols, rows), diff=diff, algo_stats=stats,
                                         activity=["x"], color=True)
                assert frame.count("\n") + 1 <= rows, (cols, rows)
                for line in frame.split("\n"):
                    assert len(_ANSI.sub("", line)) <= cols, (cols, rows, line)


# ---- the per-task heatmap (generic across algorithms) ----------------------

def test_heatmap_distinguishes_an_unevaluated_task_from_a_zero():
    """A task a candidate never ran is missing data, never a measured 0.0."""
    from cap_evolve import tui
    reduced = {
        "summary": {"tasks": ["t1", "t2", "t3"], "best_id": "c1"},
        "graph": {"root": "seed", "nodes": [
            {"id": "seed", "iteration": 0, "per_task": {"t1": 0.0, "t2": 1.0, "t3": 0.5}},
            # a free-form/agentic run may score a SUBSET: t3 was not evaluated
            {"id": "c1", "iteration": 1, "parent": "seed",
             "per_task": {"t1": 0.0, "t2": 1.0}, "status": "accepted"},
        ]},
    }
    out = tui.render_frame(reduced, (120, 40), color=False)
    assert "per-task val" in out
    assert "not evaluated" in out                     # the legend states it
    rows = {ln.split()[0]: ln for ln in out.split("\n") if ln.startswith(("seed", "c1"))}
    # seed measured all three; c1 measured two and shows the missing marker
    assert tui._MISSING not in rows["seed"][:60]
    assert tui._MISSING in rows["c1"]
    # a measured 0.0 renders as the low glyph, NOT as the missing marker
    assert tui._HEAT[0] in rows["seed"]


def test_heatmap_is_omitted_when_no_per_task_data_exists():
    from cap_evolve import tui
    assert not tui.has_per_task({"nodes": [{"id": "a"}, {"id": "b", "per_task": {}}]})
    out = tui.render_frame({"summary": {"tasks": ["t1"]},
                            "graph": {"nodes": [{"id": "a", "iteration": 1}]}}, (100, 40))
    assert "per-task" not in out


def test_heatmap_ids_are_sanitized():
    from cap_evolve import tui
    reduced = {"summary": {"tasks": ["t1"], "best_id": "x"},
               "graph": {"nodes": [{"id": "c\x1b[2J1", "iteration": 1,
                                    "per_task": {"t1": 1.0}}]}}
    out = tui.render_frame(reduced, (100, 40), color=False)
    assert "\x1b" not in out


def test_heatmap_handles_many_tasks_and_says_how_many_it_hid():
    from cap_evolve import tui
    tasks = [f"t{i}" for i in range(400)]
    reduced = {"summary": {"tasks": tasks, "best_id": "c1"},
               "graph": {"nodes": [{"id": "c1", "iteration": 1,
                                    "per_task": {t: 1.0 for t in tasks}}]}}
    out = tui.render_frame(reduced, (100, 40), color=False)
    assert "…" in out
    for line in out.split("\n"):
        assert len(line) <= 100


# ---- per-algorithm extras (capability-gated) -------------------------------

def test_fold_algo_stats_counts_only_what_the_log_contains():
    from cap_evolve.tui import fold_algo_stats
    stats = {}
    for ev in [{"kind": "gepa_select", "parent": "g1", "strategy": "pareto"},
               {"kind": "gepa_local_gate", "passed": True},
               {"kind": "gepa_local_gate", "passed": False},
               {"kind": "gepa_val_gate", "candidate": "g1"},
               "not-an-event", {}, {"kind": "_follow_end"}]:
        fold_algo_stats(ev, stats)
    assert stats["kinds"] == {"gepa_select": 1, "gepa_local_gate": 2, "gepa_val_gate": 1}
    assert stats["mb_pass"] == 1 and stats["mb_fail"] == 1
    assert stats["strategy"] == "pareto"
    fold_algo_stats({"kind": "step"}, None)          # tolerates no accumulator


def test_algo_panel_names_gepa_and_skillopt_but_never_guesses():
    from cap_evolve.tui import algo_panel
    name, bits = algo_panel({"kinds": {"gepa_select": 3, "gepa_val_gate": 1},
                             "mb_pass": 2, "mb_fail": 1}, {"frontier": 4})
    assert name == "gepa"
    joined = " ".join(bits)
    assert "parent picks 3" in joined and "minibatch gate 2✓ 1✗" in joined
    assert "pareto frontier 4" in joined

    name, bits = algo_panel({"kinds": {"skillopt_step": 2, "skillopt_slow_update": 1},
                             "epoch": "2", "epochs": "6", "lr": "4",
                             "lr_schedule": "cosine"}, {})
    assert name == "skillopt"
    joined = " ".join(bits)
    assert "epoch 2/6" in joined and "edit budget 4 (cosine)" in joined

    # hill-climb and an agent-driven run emit the same `step` events: name neither.
    assert algo_panel({"kinds": {"step": 5, "evaluate": 9}}, {}) == ("", [])
    assert algo_panel(None, {}) == ("", [])
    assert algo_panel({}, {}) == ("", [])


def test_algo_panel_values_are_sanitized():
    from cap_evolve import tui
    stats = {}
    tui.fold_algo_stats({"kind": "gepa_select", "parent": "p",
                         "strategy": "evil\x1b[2J"}, stats)
    out = tui.render_frame({"summary": {}, "graph": {"nodes": []}}, (100, 40),
                           algo_stats=stats, color=False)
    assert "\x1b" not in out
    assert "algorithm  gepa" in out


def test_algo_panel_is_absent_when_the_algorithm_is_not_evidenced():
    from cap_evolve import tui
    out = tui.render_frame({"summary": {}, "graph": {"nodes": []}}, (100, 40),
                           algo_stats={"kinds": {"step": 3}})
    assert "algorithm" not in out


# ---- the diff panel --------------------------------------------------------

def test_diff_panel_renders_and_states_what_it_cropped():
    from cap_evolve import tui
    diff = {"title": "seed → c1  1 file  +2 -0",
            "lines": [f"  + line {i}" for i in range(30)]}
    out = tui.render_frame({"summary": {}, "graph": {"nodes": []}}, (100, 40),
                           diff=diff, color=False)
    assert "changes" in out and "seed → c1" in out
    assert "more line(s)" in out and "cap-evolve diff" in out


def test_diff_panel_content_is_sanitized_and_cropped():
    from cap_evolve import tui
    diff = {"title": "a\x1b[2J → b", "lines": ["  + " + "x" * 500]}
    out = tui.render_frame({"summary": {}, "graph": {"nodes": []}}, (80, 40),
                           diff=diff, color=False)
    assert "\x1b" not in out
    for line in out.split("\n"):
        assert len(line) <= 80


def test_crop_ansi_counts_visible_columns_only():
    from cap_evolve.tui import _crop_ansi
    plain = _ANSI.sub("", _crop_ansi("\x1b[32mabcdef\x1b[0m", 3))
    assert plain == "abc"
    assert _crop_ansi("abcdef", 3) == "abc"
    assert _crop_ansi("", 5) == ""
    # never ends mid-escape
    assert not _crop_ansi("\x1b[32mabc", 2).endswith("\x1b[")


def test_latest_diff_returns_none_without_snapshots():
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        root = _mk_run(Path(d))
        assert tui.latest_diff(root, tui._reduce(root), 100, color=False) is None


def test_latest_diff_reads_the_accepted_candidates_snapshot():
    from cap_evolve import tui
    with tempfile.TemporaryDirectory() as d:
        root = _mk_run(Path(d))
        for name, text in (("seed", "one\n"), ("cand_0001", "one\ntwo\n")):
            p = root / "candidates" / name
            p.mkdir(parents=True)
            (p / "prompt.txt").write_text(text, encoding="utf-8")
        got = tui.latest_diff(root, tui._reduce(root), 100, color=False)
        assert got and "seed → cand_0001" in got["title"]
        assert any("two" in ln for ln in got["lines"])


# ---- the brand headline ----------------------------------------------------

def test_headline_is_skipped_without_color_and_on_a_short_terminal():
    import io

    from cap_evolve import tui

    class _S(io.StringIO):
        def isatty(self):
            return True

    buf = _S()
    assert tui.headline(buf, color=False) == 0
    assert buf.getvalue() == ""


def test_spend_split_omits_roles_with_no_recorded_spend():
    from cap_evolve import tui
    reduced = {"summary": {"cost": {"runner_usd": 0.0, "optimizer_usd": 1.25,
                                    "intake_usd": 0.0, "total_usd": 1.25}},
               "graph": {"nodes": []}}
    out = tui.render_frame(reduced, (120, 40), color=False)
    assert "optimizer $1.2500" in out
    assert "runner $" not in out          # never a fabricated $0.0000
    assert "intake $" not in out
