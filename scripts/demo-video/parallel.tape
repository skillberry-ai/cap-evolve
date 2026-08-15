Output "/tmp/video/parallel.mp4"

Set Shell "bash"
Set FontFamily "Menlo"
# Big type in a SHORT window, so the 8 lines par_demo.py actually prints fill the
# composition after build.sh scales the clip to fit 2560x1440. Recorded at
# 2560x1440 with FontSize 28 this shot was ~90% empty frame.
Set FontSize 56
Set Width 2560
Set Height 760
Set Padding 40
Set Margin 0
Set Theme { "background": "#0b0d17", "foreground": "#e6edf3", "black": "#0b0d17", "red": "#ff6b81", "green": "#4ade80", "yellow": "#fbbf24", "blue": "#60a5fa", "magenta": "#a78bfa", "cyan": "#22d3ee", "white": "#e6edf3", "brightBlack": "#6b7280", "brightRed": "#ff8fa3", "brightGreen": "#86efac", "brightYellow": "#fcd34d", "brightBlue": "#93c5fd", "brightMagenta": "#c4b5fd", "brightCyan": "#67e8f9", "brightWhite": "#ffffff", "cursorColor": "#7c5cff", "selectionBackground": "#312e81" }

Hide
Type "cd $(git rev-parse --show-toplevel)"
Enter
Type "clear"
Enter
Sleep 1s
Show

Type "# same 16 tasks x 2 trials, same deterministic adapter"
Enter
Sleep 1500ms
Type "python scripts/demo-video/par_demo.py"
Sleep 600ms
Enter
Sleep 15s
