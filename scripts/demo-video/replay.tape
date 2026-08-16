Output "/tmp/video/replay.mp4"

Set Shell "bash"
Set FontFamily "Menlo"
# 28, not 24: see the note below on why 28 and not larger. At 2560 wide, FontSize 24 gives ~170 columns and the run is
# unreadable once the video is scaled to a README/YouTube player. 34 gives ~120
# columns — still wide enough for the TUI's lineage rows not to wrap, and roughly
# 17 CSS px when the 2560px frame is displayed at half size.
Set FontSize 28
Set Width 2560
Set Height 1440
Set Padding 40
Set Margin 0
# 30, not 60: with Framerate 60 vhs writes ~25fps of captured frames but stamps
# the file 60fps, so the mp4 comes out half as long as the tape and plays ~2x
# too fast to read. At 30 the output duration matches wall time.
Set Framerate 30
Set Theme { "background": "#0b0d17", "foreground": "#e6edf3", "black": "#0b0d17", "red": "#ff6b81", "green": "#4ade80", "yellow": "#fbbf24", "blue": "#60a5fa", "magenta": "#a78bfa", "cyan": "#22d3ee", "white": "#e6edf3", "brightBlack": "#6b7280", "brightRed": "#ff8fa3", "brightGreen": "#86efac", "brightYellow": "#fcd34d", "brightBlue": "#93c5fd", "brightMagenta": "#c4b5fd", "brightCyan": "#67e8f9", "brightWhite": "#ffffff", "cursorColor": "#7c5cff", "selectionBackground": "#312e81" }

Hide
Type "cd $(git rev-parse --show-toplevel)"
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
