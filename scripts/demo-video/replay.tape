Output "/tmp/video/replay.mp4"

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 24
Set Width 2560
Set Height 1340
Set Padding 40
Set Margin 0
Set Framerate 60
Set Theme { "background": "#0b0d17", "foreground": "#e6edf3", "black": "#0b0d17", "red": "#ff6b81", "green": "#4ade80", "yellow": "#fbbf24", "blue": "#60a5fa", "magenta": "#a78bfa", "cyan": "#22d3ee", "white": "#e6edf3", "brightBlack": "#6b7280", "brightRed": "#ff8fa3", "brightGreen": "#86efac", "brightYellow": "#fcd34d", "brightBlue": "#93c5fd", "brightMagenta": "#c4b5fd", "brightCyan": "#67e8f9", "brightWhite": "#ffffff", "cursorColor": "#7c5cff", "selectionBackground": "#312e81" }

Hide
Type "cd \"$(git rev-parse --show-toplevel)\" && clear"
Enter
Sleep 1s
Show

Type "cap-evolve replay --demo --speed 3 --max-gap 4.0"
Sleep 900ms
Enter
Sleep 50s
