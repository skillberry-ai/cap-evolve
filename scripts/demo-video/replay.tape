Output "/tmp/video/replay.mp4"

Set Shell "bash"
Set FontFamily "Menlo"
# FontSize 28 with Height 1440 gives exactly 40 rows, which is what the home
# screen needs for its FULL command table (home() condenses the table to 3 rows
# below ~23 rows). Do not raise it: at 34 the cell is 41px, only 33 rows fit, and
# the home screen scrolls the capybara off the top. Text size in the finished
# 1440p frame is FontSize x (1440/Height), so 40 rows at 1440 is the ceiling —
# nothing is gained by trading rows for a bigger glyph.
Set FontSize 28
# 2010, not 2560: at 2560 this is a 144-column terminal, and the home screen's
# content is only ~87 columns wide, so it sat hard left with 1005px (39%) of the
# frame dead on the right and read as a broken render. 2010 gives 112 columns —
# build.sh's NORM (force_original_aspect_ratio=decrease + centred pad) then
# pillarboxes the 2010x1440 recording symmetrically inside 2560x1440.
# Why 112 and not the 105-110 that pure symmetry wants: the CLI's demo
# disclaimer (tui.DEMO_BANNER) is 119 chars and the terminal hard-wraps it
# mid-word at every width from 104 to 111 ("no benc / hmark claim"). 112 is the
# narrowest width >=105 that breaks it on a space. Nothing is stretched: the
# recording keeps its aspect and is centred, never scaled to fill.
Set Width 2010
Set Height 1440
Set Padding 40
Set Margin 0
# 30, not 60: with Framerate 60 vhs writes ~25fps of captured frames but stamps
# the file 60fps, so the mp4 comes out half as long as the tape and plays ~2x
# too fast to read. At 30 the output duration matches wall time.
Set Framerate 30
Set Theme { "background": "#0b0d17", "foreground": "#e6edf3", "black": "#0b0d17", "red": "#ff6b81", "green": "#4ade80", "yellow": "#fbbf24", "blue": "#60a5fa", "magenta": "#a78bfa", "cyan": "#22d3ee", "white": "#e6edf3", "brightBlack": "#6b7280", "brightRed": "#ff8fa3", "brightGreen": "#86efac", "brightYellow": "#fcd34d", "brightBlue": "#93c5fd", "brightMagenta": "#c4b5fd", "brightCyan": "#67e8f9", "brightWhite": "#ffffff", "cursorColor": "#7c5cff", "selectionBackground": "#312e81" }

Hide
# `cd $(git rev-parse ...)` alone is a TRAP: run vhs from outside a repo and
# rev-parse fails, `cd` with no argument goes to $HOME, PYTHONPATH=core points at
# nothing, and `python -m cap_evolve.cli` silently answers from whatever cap_evolve
# is installed — i.e. a DIFFERENT clone. That records a plausible-looking video of
# the wrong software, which cost two takes to notice. So exit instead: a truncated
# recording fails build.sh's seek loudly, and a loud failure beats a quiet lie.
Type "cd $(git rev-parse --show-toplevel) && test -f core/cap_evolve/cli.py || exit 1"
Enter
# COLORTERM=truecolor is what unlocks the capybara mark in branding.py; at any
# lower colour depth the home screen falls back to the wordmark alone.
Type "export COLORTERM=truecolor PYTHONPATH=core PS1='$ '"
Enter
# Run THIS checkout's rebuilt CLI, not whichever cap-evolve happens to be on
# PATH (on this machine that resolves to a different clone). Everything on
# camera is real output from core/cap_evolve.
Type `cap-evolve() { python -m cap_evolve.cli "$@"; }`
Enter
# ...and PROVE the shim resolves to this checkout rather than an installed copy.
# This is the invariant the whole recording rests on, so assert it, don't assume it.
Type `python -c "import cap_evolve,pathlib,sys; sys.exit(0 if pathlib.Path(cap_evolve.__file__).resolve().parents[1]==pathlib.Path('core').resolve() else 1)" || exit 1`
Enter
Type "clear"
Enter
Sleep 1s
Show

# ── beat 1: open the CLI ──────────────────────────────────────────────────
# The branded home screen: capybara mark, wordmark, the golden path, and the
# command groups. This is the "what am I even looking at" shot.
Type "cap-evolve"
Sleep 500ms
Enter
Sleep 4s

Hide
Type "clear"
Enter
Sleep 400ms
Show

# ── beat 2: the phases of a run ───────────────────────────────────────────
# replay re-feeds the bundled demo session through the SAME live view a real run
# renders: run_config + frozen splits (intake), the seed baseline, then one
# candidate per iteration with the gate's ACCEPT / reject / indecisive verdict
# and its arithmetic, and finally FINALIZE on the sealed test split.
# --speed/--max-gap only compress the recorded inter-event gaps; every number,
# verdict and line of layout is the real renderer's.
Type "cap-evolve replay --demo --speed 40 --max-gap 0.7"
Sleep 500ms
Enter
Sleep 15s
