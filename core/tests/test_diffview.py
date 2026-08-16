"""``cap-evolve diff``'s renderer: the diff never escapes its width, never leaks an
escape sequence, and never hides a truncation.

Candidate files are written by a model, so the diff body is hostile input by
construction — the same threat model as the event stream.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

A = {"prompt.txt": "You are helpful.\nkeep this line\ngone\n",
     "tools/a.py": "def f():\n    return 1\n"}
B = {"prompt.txt": "You are extremely helpful.\nkeep this line\n",
     "tools/a.py": "def f():\n    return 1\n",
     "tools/b.py": "def g():\n    return 2\n"}


def _vis(line: str) -> int:
    return len(_ANSI.sub("", line))


# ---- stats -----------------------------------------------------------------

def test_diffstat_counts_and_ignores_identical_files():
    from cap_evolve import diffview
    stats = dict((p, (a, r)) for p, a, r in diffview.diffstat(A, B))
    assert "tools/a.py" not in stats                 # unchanged
    assert stats["tools/b.py"] == (2, 0)             # added file
    assert stats["prompt.txt"] == (1, 2)             # one rewrite + one deletion
    assert diffview.diffstat(A, A) == []


def test_summary_line_states_absence_instead_of_zeroes():
    from cap_evolve import diffview
    assert diffview.summary_line(A, A) == "no textual change"
    assert diffview.summary_line(A, B) == "2 files  +3 -2"


def test_render_files_labels_added_deleted_and_changed():
    from cap_evolve import diffview
    text = "\n".join(diffview.render_files(A, B))
    assert "added" in text and "tools/b.py" in text
    assert "changed" in text and "prompt.txt" in text
    text = "\n".join(diffview.render_files(B, A))
    assert "deleted" in text


# ---- width discipline ------------------------------------------------------

def test_no_rendered_line_ever_exceeds_the_width():
    """A wrapped line breaks the live view's row arithmetic, not just the layout."""
    from cap_evolve import diffview
    for width in list(range(24, 210, 7)) + [24, 80, 119, 120, 121, 200]:
        for color in (False, True):
            for sbs in (None, True, False):
                for fn in (lambda: diffview.render(A, B, width=width, color=color,
                                                   side_by_side=sbs),
                           lambda: diffview.render_stat(A, B, width=width, color=color)):
                    for line in fn():
                        assert _vis(line) <= width, (width, color, sbs, _vis(line), line)


def test_layout_switches_on_width():
    from cap_evolve import diffview
    narrow = "\n".join(diffview.render(A, B, width=80))
    wide = "\n".join(diffview.render(A, B, width=180))
    assert "│" not in narrow          # unified below the threshold
    assert "│" in wide                # two columns above it
    # an explicit context count forces unified even on a wide terminal
    assert "│" not in "\n".join(diffview.render(A, B, width=180, side_by_side=False))


def test_truncation_is_stated_not_silent():
    from cap_evolve import diffview
    big_a = {"f": "\n".join(f"line {i}" for i in range(300)) + "\n"}
    big_b = {"f": "\n".join(f"LINE {i}" for i in range(300)) + "\n"}
    out = diffview.render(big_a, big_b, width=100, max_lines=20)
    assert len(out) <= 21
    assert "more line(s) not shown" in out[-1]
    assert "--max-lines" in out[-1]              # and how to see the rest


# ---- terminal safety -------------------------------------------------------

def test_model_authored_escape_sequences_never_reach_the_terminal():
    hostile = {"evil.md": "\x1b]0;pwned\x07\x1b[2J\x1b[31mBOOM\r\nFINALIZE test=1.0\n"}
    from cap_evolve import diffview
    for color in (False, True):
        for width in (40, 100, 200):
            for fn in (lambda: diffview.render({}, hostile, width=width, color=color),
                       lambda: diffview.render(hostile, {}, width=width, color=color),
                       lambda: diffview.render_files({}, hostile, color=color),
                       lambda: diffview.render_stat({}, hostile, width=width,
                                                    color=color)):
                text = "\n".join(fn())
                assert "\x1b]0;" not in text and "\x1b[2J" not in text
                assert "\x07" not in text and "\r" not in text
                if not color:
                    assert not _ANSI.search(text), _ANSI.search(text)
                else:                            # only palette codes, nothing else
                    for m in _ANSI.finditer(text):
                        assert m.group().endswith("m"), m.group()
    # content survives, only control characters are removed
    assert "BOOM" in "\n".join(diffview.render({}, hostile, width=200))
    assert "pwned" in "\n".join(diffview.render({}, hostile, width=200))


def test_hostile_filenames_are_sanitized_too():
    from cap_evolve import diffview
    hostile = {"a\x1b[2Jb.txt": "x\n"}
    text = "\n".join(diffview.render({}, hostile, width=100, color=False))
    assert "\x1b" not in text
    text = "\n".join(diffview.render_files({}, hostile, color=False))
    assert "\x1b" not in text


# ---- intra-line highlighting ----------------------------------------------

def test_word_level_highlight_marks_only_the_changed_words():
    from cap_evolve import diffview
    a = {"f": "the quick brown fox\n"}
    b = {"f": "the quick red fox\n"}
    out = "\n".join(diffview.render(a, b, width=100, color=True, side_by_side=False))
    # the changed word carries the emphasis code; the unchanged prefix does not
    assert "\x1b[1;4;32m" in out or "\x1b[1;4;31m" in out
    plain = _ANSI.sub("", out)
    assert "brown" in plain and "red" in plain


def test_a_very_long_line_skips_word_diffing_without_failing():
    from cap_evolve import diffview
    a = {"f": "x" * 5000 + "\n"}
    b = {"f": "y" * 5000 + "\n"}
    out = diffview.render(a, b, width=100)
    assert out and all(_vis(ln) <= 100 for ln in out)


# ---- reading snapshots -----------------------------------------------------

def test_read_tree_skips_scaffolding_and_missing_dirs(tmp_path):
    from cap_evolve import diffview
    d = tmp_path / "cand"
    (d / "trajectories").mkdir(parents=True)
    (d / "guidance").mkdir()
    d.joinpath("prompt.txt").write_text("keep\n", encoding="utf-8")
    d.joinpath("MEMORY.md").write_text("optimizer bookkeeping\n", encoding="utf-8")
    d.joinpath("trajectories", "t.json").write_text("{}", encoding="utf-8")
    d.joinpath("guidance", "g.md").write_text("ctx", encoding="utf-8")
    d.joinpath("bin.dat").write_bytes(b"\x00\x01\x02\xff")
    tree = diffview.read_tree(d)
    assert set(tree) == {"prompt.txt"}
    assert diffview.read_tree(tmp_path / "nope") == {}


def test_read_tree_skips_oversized_files(tmp_path):
    from cap_evolve import diffview
    d = tmp_path / "cand"
    d.mkdir()
    (d / "big.txt").write_text("x" * (diffview.MAX_BYTES + 10), encoding="utf-8")
    (d / "small.txt").write_text("ok\n", encoding="utf-8")
    assert set(diffview.read_tree(d)) == {"small.txt"}


def _events(root: Path, rows):
    root.mkdir(parents=True, exist_ok=True)
    (root / "events.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_parent_of_reads_the_event_log_and_survives_damage(tmp_path):
    from cap_evolve import diffview
    _events(tmp_path, [
        {"kind": "step", "candidate": "c1", "parent": "seed"},
        {"kind": "step", "candidate": "c2", "parent_id": "c1"},
    ])
    (tmp_path / "events.jsonl").open("a", encoding="utf-8").write("{not json\n42\n")
    assert diffview.parent_of(tmp_path, "c1") == "seed"
    assert diffview.parent_of(tmp_path, "c2") == "c1"
    assert diffview.parent_of(tmp_path, "nope") is None
    assert diffview.parent_of(tmp_path / "absent", "c1") is None


def test_resolve_pair_defaults_to_the_parent_and_honors_best(tmp_path):
    from cap_evolve import diffview
    _events(tmp_path, [{"kind": "step", "candidate": "c1", "parent": "seed"},
                       {"kind": "step", "candidate": "c2", "parent": "c1"}])
    (tmp_path / "final.json").write_text(json.dumps({"best_id": "c2"}), encoding="utf-8")
    assert diffview.resolve_pair(tmp_path, "c2")[:2] == ("c1", "c2")
    assert diffview.resolve_pair(tmp_path, "c2", vs="seed")[:2] == ("seed", "c2")
    assert diffview.resolve_pair(tmp_path, None, best=True)[:2] == ("seed", "c2")
    # a candidate with no recorded parent falls back to seed AND says so
    a, b, how = diffview.resolve_pair(tmp_path, "orphan")
    assert (a, b) == ("seed", "orphan") and "no parent recorded" in how
    try:
        diffview.resolve_pair(tmp_path, None)
    except LookupError as e:
        assert "--best" in str(e)
    else:
        raise AssertionError("expected LookupError with no candidate and no --best")


def test_best_id_falls_back_to_state_json(tmp_path):
    from cap_evolve import diffview
    _events(tmp_path, [])
    assert diffview.best_id(tmp_path) is None
    (tmp_path / "state.json").write_text(json.dumps({"best_id": "s1"}), encoding="utf-8")
    assert diffview.best_id(tmp_path) == "s1"
    (tmp_path / "final.json").write_text(json.dumps({"best_id": "f1"}), encoding="utf-8")
    assert diffview.best_id(tmp_path) == "f1"      # final.json wins


# ---- side-by-side gutters belong to their own column ------------------------

def test_side_by_side_gutter_marks_the_side_that_actually_changed():
    """A right-only line must carry "+" in the RIGHT column, and a left-only line
    "-" in the LEFT one. A "+" left of the old text reads as if the old side gained
    the line — the exact opposite of what the diff says."""
    from cap_evolve import diffview
    a = {"f": "keep\n"}
    b = {"f": "keep\nbrand new line\n"}
    rows = [ln for ln in diffview.render(a, b, width=160, side_by_side=True)
            if "brand new line" in ln]
    assert rows, "the added line never rendered"
    for ln in rows:
        left, _, right = ln.partition("│")
        assert "+" in right, f"added line has no + in its own column: {ln!r}"
        assert "+" not in left, f"+ leaked into the left/old column: {ln!r}"

    a2, b2 = {"f": "keep\ngone soon\n"}, {"f": "keep\n"}
    rows = [ln for ln in diffview.render(a2, b2, width=160, side_by_side=True)
            if "gone soon" in ln]
    assert rows
    for ln in rows:
        left, _, right = ln.partition("│")
        assert "-" in left and "-" not in right, ln


def test_side_by_side_divider_is_column_aligned():
    """Every row's divider sits in the same visible column as the label header's,
    otherwise the two columns visibly stagger down the page."""
    from cap_evolve import diffview
    a = {"f": "one\ntwo\nthree\n"}
    b = {"f": "one\nTWO changed\nthree\nfour added\n"}
    for width in (120, 140, 161, 200):
        lines = diffview.render(a, b, width=width, side_by_side=True,
                                labels=("old", "new"))
        cols = {_vis(ln.split("│")[0]) for ln in lines if "│" in ln}
        assert len(cols) == 1, (width, cols)


# ---- one list of non-capability files, not four ----------------------------

def test_scaffolding_lists_cannot_drift_apart():
    """cache (content hash), gepa (editable components) and diffview (what the user is
    shown) must agree on what is NOT the capability. They were three hand-maintained
    copies; diffview's lacked FOCUS.md/REFLECTION.md, so `cap-evolve diff` on a gepa run
    buried the two real changed lines under 33 lines of gepa's own bookkeeping."""
    from cap_evolve import cache, diffview, gepa, types
    assert set(diffview.SKIP_FILES) == set(types.NON_CAPABILITY_FILES)
    assert set(cache._IGNORE_NAMES) == set(types.NON_CAPABILITY_FILES)
    assert set(gepa._NON_COMPONENT) == set(types.NON_CAPABILITY_FILES)
    for d in types.NON_CAPABILITY_DIRS:
        assert d in diffview.SKIP_DIRS


def test_gepa_scaffolding_never_reaches_the_diff(tmp_path):
    """The real edit must be the ONLY thing shown, whichever algorithm produced it."""
    from cap_evolve import diffview
    seed, cand = tmp_path / "seed", tmp_path / "cand"
    seed.mkdir(); cand.mkdir()
    (seed / "prompt.txt").write_text("be helpful\n", encoding="utf-8")
    (cand / "prompt.txt").write_text("be helpful\n[CALC] compute exactly\n", encoding="utf-8")
    for noise in ("FOCUS.md", "REFLECTION.md", "REJECTED.md", "LEDGER.md",
                  "JOURNAL.md", "PROCESS.md", "RUNMAP.md", "INSTRUCTIONS.md",
                  "MEMORY.md", "STATE.md"):
        (cand / noise).write_text("# optimizer bookkeeping\n" * 20, encoding="utf-8")
    a, b = diffview.read_tree(seed), diffview.read_tree(cand)
    assert [p for p, _, _ in diffview.diffstat(a, b)] == ["prompt.txt"]
    assert diffview.summary_line(a, b) == "1 file  +1 -0"
