Output "/tmp/video/replay.mp4"

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 24
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
Type "export COLORTERM=truecolor"
Enter
Type "clear"
Enter
Sleep 1s
Show

# --speed 20 --max-gap 1.4 compresses the recorded 25m53s session into ~16s of
# real time, so build.sh's 13.7s window can BUILD: it opens partway down the
# lineage and lands on the finished frame with accept + reject + indecisive all
# on screen. Slower settings put the interesting rows past the end of the shot.
Type "cap-evolve replay --demo --speed 20 --max-gap 1.4"
Sleep 400ms
Enter
Sleep 22s
