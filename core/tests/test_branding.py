"""The brand surface: every screen is ANSI-free without color, the capybara only
exists where it can render, and the command catalog cannot drift from the CLI.

Every assertion here is a pure function call — no terminal, no run, no subprocess.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _screens(width, color):
    from cap_evolve import branding
    env = {} if color else {"NO_COLOR": "1"}
    return {
        "home": branding.home(width, color=color, env=env, version="9.9.9"),
        "help_index": branding.help_for(None, width, color=color, env=env),
        "help_diff": branding.help_for("diff", width, color=color, env=env),
        "help_bogus": branding.help_for("nope", width, color=color, env=env),
        "algorithms": branding.algorithms_screen(None, width, color=color, env=env),
        "algorithms_one": branding.algorithms_screen("gepa", width, color=color, env=env),
        "banner": branding.banner(width, color=color, env=env),
        "masthead": branding.banner(width, color=color, env=env, lines=("",), pairs=(
            ("run", "run_x"), ("algorithm", "hill-climb · deterministic"),
            ("spec", "/very/long/path/to/a/project/capevolve.yaml"),
            ("split", "train 8 · val 6 · test 6   seed 0"),
            ("gate", "paired   k_se 0.20   trials 2"), ("target", "m-1"))),
    }


# ---- the masthead (the block beside the logo) -------------------------------

def test_masthead_pairs_render_beside_the_logo_and_stay_inside_the_width():
    from cap_evolve import branding
    for width in (64, 80, 100, 200):
        lines = _screens(width, False)["masthead"]
        text = "\n".join(lines)
        assert "run_x" in text and "hill-climb · deterministic" in text
        # aligned label column: every value starts at the same offset
        starts = {ln.index("run_x") for ln in lines if "run_x" in ln}
        assert len(starts) == 1
        for ln in lines:
            assert len(_ANSI.sub("", ln)) <= width, (width, ln)
    # exactly LOGO_ROWS rows in truecolor: the block ends level with the capybara
    art = _screens(100, True)["masthead"]
    assert len(art) == branding.LOGO_ROWS
    # a long value is cropped, not wrapped onto a row the logo does not have
    narrow = branding.banner(70, color=False, env={"NO_COLOR": "1"},
                             pairs=(("spec", "x" * 300),))
    assert all(len(ln) <= 70 for ln in narrow)


# ---- ANSI discipline --------------------------------------------------------

def test_every_screen_is_ansi_free_without_color():
    for width in (24, 40, 64, 80, 100, 200):
        for name, lines in _screens(width, False).items():
            for line in lines:
                assert not _ANSI.search(line), (name, width, line)


def test_color_depth_honors_no_color_and_dumb_terminals():
    from cap_evolve.branding import color_depth
    assert color_depth(True, {"COLORTERM": "truecolor"}) == "truecolor"
    assert color_depth(True, {"COLORTERM": "24bit"}) == "truecolor"
    assert color_depth(True, {"TERM": "xterm-direct"}) == "truecolor"
    assert color_depth(True, {"TERM": "xterm-256color"}) == "ansi"
    assert color_depth(True, {}) == "ansi"
    # every "no" path
    assert color_depth(False, {"COLORTERM": "truecolor"}) == "none"
    assert color_depth(True, {"NO_COLOR": "1", "COLORTERM": "truecolor"}) == "none"
    assert color_depth(True, {"TERM": "dumb", "COLORTERM": "truecolor"}) == "none"


def test_colored_screens_carry_only_sgr_codes():
    """Styling only: no cursor moves, no OSC, nothing that could reposition output."""
    for name, lines in _screens(100, True).items():
        for line in lines:
            for m in _ANSI.finditer(line):
                assert m.group().endswith("m"), (name, m.group())
            assert "\x1b]" not in line and "\x07" not in line, name


# ---- the mark ---------------------------------------------------------------

def test_logo_pixels_are_well_formed():
    from cap_evolve import branding
    rows = branding.LOGO_PIXELS.strip("\n").split("\n")
    assert len(rows) == branding.LOGO_ROWS
    for row in rows:
        assert len(row) == branding.LOGO_COLS * 12, len(row)
        for i in range(0, len(row), 6):
            cell = row[i:i + 6]
            assert cell == "......" or re.fullmatch(r"[0-9a-f]{6}", cell), cell


def test_logo_renders_only_in_truecolor():
    from cap_evolve import branding
    assert branding.logo_lines("none") == []
    assert branding.logo_lines("ansi") == []          # no 256/16 tier, by design
    art = branding.logo_lines("truecolor")
    assert len(art) == branding.LOGO_ROWS
    assert all("▀" in ln or "▄" in ln for ln in art)


def test_banner_drops_the_art_when_it_cannot_render():
    from cap_evolve import branding
    wide = branding.banner(100, color=True, env={"COLORTERM": "truecolor"})
    assert len(wide) == max(branding.LOGO_ROWS, 2)
    # too narrow → wordmark only, even in truecolor
    narrow = branding.banner(branding.MIN_LOGO_COLS - 1, color=True,
                             env={"COLORTERM": "truecolor"})
    assert len(narrow) == 2
    # no color → wordmark only
    assert len(branding.banner(200, color=False)) == 2


def test_wordmark_and_tagline_are_present():
    from cap_evolve import branding
    text = "\n".join(branding.home(100, color=False, env={"NO_COLOR": "1"}))
    assert "cap-evolve" in text
    assert branding.TAGLINE in text


# ---- the catalog cannot drift ----------------------------------------------

def test_catalog_and_cli_commands_agree():
    from cap_evolve import branding, cli
    assert set(branding.COMMANDS) == set(cli.COMMANDS), (
        set(branding.COMMANDS) ^ set(cli.COMMANDS))


def test_every_command_documents_usage_and_runnable_examples():
    from cap_evolve import branding
    for name, meta in branding.COMMANDS.items():
        assert meta["summary"] and not meta["summary"].endswith("."), name
        assert meta["usage"].startswith(f"cap-evolve {name}"), name
        assert meta["examples"], name
        for ex in meta["examples"]:
            assert ex.startswith("cap-evolve "), (name, ex)
            assert name in ex, (name, ex)


def test_home_shows_the_golden_path_and_every_command():
    from cap_evolve import branding
    text = "\n".join(branding.home(100, color=False, env={"NO_COLOR": "1"}))
    for step in ("cap-evolve init", "cap-evolve doctor", "cap-evolve run --tui"):
        assert step in text, step
    for name in branding.COMMANDS:
        assert name in text, name


# ---- the algorithm chooser matches the shipped skills ----------------------

def test_algorithms_cover_every_shipped_algorithm_skill():
    from cap_evolve import branding
    skills = REPO / "skills" / "algorithms"
    if not skills.is_dir():           # installed without the skill library
        return
    shipped = {p.name for p in skills.iterdir() if p.is_dir()}
    assert shipped == set(branding.ALGORITHMS), shipped ^ set(branding.ALGORITHMS)


def test_every_algorithm_prints_the_exact_spec_lines_that_select_it():
    from cap_evolve import branding
    for name, meta in branding.ALGORITHMS.items():
        assert meta["mode"] in ("agent", "deterministic"), name
        assert any(ln.startswith("algorithm_skill:") for ln in meta["spec"]), name
        assert f"algorithm_skill: {name}" in meta["spec"], name
        # an agent-driven algorithm must say so in the lines you paste
        if meta["mode"] == "agent":
            assert "orchestration_mode: agent" in meta["spec"], name
    text = "\n".join(branding.algorithms_screen(None, 100, color=False,
                                                env={"NO_COLOR": "1"}))
    for name in branding.ALGORITHMS:
        assert f"algorithm_skill: {name}" in text, name


# ---- the home screen must FIT, not scroll ----------------------------------

_TRUECOLOR = {"COLORTERM": "truecolor"}


def _visible(lines):
    import re
    ansi = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
    return [ansi.sub("", ln) for ln in lines]


def test_home_fits_an_80x24_terminal():
    """The regression that matters: at 80x24 the home screen was 36 rows and 88 columns,
    so it scrolled and wrapped. The user saw the BOTTOM — the version line — with the
    capybara, the wordmark, the tagline and the whole golden path already gone off the
    top. The brand is exactly the part that got lost, on a user's first command."""
    from cap_evolve import branding
    for color, env in ((True, _TRUECOLOR), (True, {}), (False, {})):
        lines = branding.home(80, color=color, env=env, version="0.1.0", rows=24)
        vis = _visible(lines)
        # one row belongs to the shell line the command was typed on
        assert len(lines) <= 24 - branding.HOME_PROMPT_ROWS, (color, env, len(lines))
        assert max(len(v) for v in vis) <= 80, (color, env, max(len(v) for v in vis))


def test_home_fits_every_plausible_terminal():
    from cap_evolve import branding
    for w in (40, 64, 70, 80, 100, 120, 160, 204):
        for h in (10, 14, 18, 20, 24, 30, 40, 50, 52, 200):
            lines = branding.home(w, color=True, env=_TRUECOLOR, version="0.1.0", rows=h)
            vis = _visible(lines)
            assert len(lines) <= h - branding.HOME_PROMPT_ROWS or h <= 4, (w, h, len(lines))
            assert max((len(v) for v in vis), default=0) <= w, (w, h)


def test_home_never_loses_the_brand_or_the_golden_path_when_it_shrinks():
    """Degrading may drop detail; it must not drop identity or the first thing to run."""
    from cap_evolve import branding
    for h in (18, 20, 24, 30):
        text = "\n".join(_visible(branding.home(80, color=False, version="0.1.0", rows=h)))
        assert "cap-evolve" in text
        assert branding.TAGLINE in text
        assert "Golden path" in text
        assert "cap-evolve init" in text


def test_home_still_names_every_command_in_the_compact_form():
    """Condensing the table must not hide a command — the compact form lists the names."""
    from cap_evolve import branding
    text = "\n".join(_visible(branding.home(80, color=False, version="0.1.0", rows=24)))
    for name in branding.COMMANDS:
        assert name in text, name
    for group in branding._GROUP_ORDER:
        assert group in text, group


def test_home_uses_the_full_table_when_there_is_room():
    """A tall terminal should get the summaries, not the permanently-compact form."""
    from cap_evolve import branding
    tall = "\n".join(_visible(branding.home(120, color=False, version="0.1.0", rows=60)))
    short = "\n".join(_visible(branding.home(120, color=False, version="0.1.0", rows=24)))
    assert branding.COMMANDS["init"]["summary"] in tall
    assert branding.COMMANDS["init"]["summary"] not in short
    assert len(tall.splitlines()) > len(short.splitlines())


def test_home_unlimited_rows_is_the_full_screen():
    from cap_evolve import branding
    assert branding.home(120, color=False, version="0.1.0", rows=None) == \
        branding.home(120, color=False, version="0.1.0", rows=999)


def test_home_drops_a_hint_explanation_rather_than_clipping_it_mid_word():
    """A narrow terminal must not leave a half-word behind.

    Width-clipping the trailing grey explanation produced "...a real session
    through th", which reads as a broken renderer. The label and the command are
    the payload, so the explanation is dropped instead — and comes back when
    there is room for it.
    """
    from cap_evolve import branding
    why = "replays a real session through the live view"

    narrow = "\n".join(_visible(branding.home(80, color=False, version="0.1.0", rows=24)))
    wide = "\n".join(_visible(branding.home(120, color=False, version="0.1.0", rows=24)))

    # the command a user has to type survives at both widths
    assert "cap-evolve replay --demo" in narrow
    assert "cap-evolve replay --demo" in wide
    # the explanation appears in full, or not at all — never as a fragment.
    # Checked on the hint LINE itself: a substring scan over the whole screen
    # false-positives on unrelated text ("  Golden path" ends in "th").
    assert why in wide
    assert why not in narrow
    hint = next(ln for ln in narrow.splitlines() if "no API key?" in ln)
    assert hint.rstrip().endswith("cap-evolve replay --demo"), hint
    for n in range(6, len(why)):                    # no proper prefix of `why` survives
        assert not hint.rstrip().endswith(why[:n]), f"clipped mid-explanation: {hint!r}"


def test_home_never_exceeds_its_width():
    """Every offered width, including ones that force the compact table."""
    from cap_evolve import branding
    for width in (60, 72, 80, 100, 120, 204):
        for rows in (24, 40, None):
            lines = _visible(branding.home(width, color=False, version="0.1.0", rows=rows))
            worst = max((len(ln) for ln in lines), default=0)
            assert worst <= width, f"width={width} rows={rows}: line of {worst} chars"
