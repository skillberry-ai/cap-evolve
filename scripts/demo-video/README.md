# Demo video sources

Regenerates `docs/assets/demo/cap-evolve-demo.mp4` — the README demo. Committed so the
video is reproducible rather than a one-off screen recording nobody can rebuild.

The recorded terminal segments come from `cap-evolve replay --demo`, which replays the
committed `core/cap_evolve/demo_session/events.jsonl` through the **real** TUI renderer.
Nothing in the footage is mocked: the frames are what the live `cap-evolve watch` draws.

> The demo session's *numbers* are hand-authored and make **no benchmark claim** — the
> banner says so on screen at both ends. Real measured results live in `docs/RESULTS.md`.
> The parallel segment is the one number measured live on camera.

## Requirements

| Tool | Why |
|---|---|
| [`vhs`](https://github.com/charmbracelet/vhs) | renders a scripted terminal to mp4 with a real font, so text stays crisp at 1440p (a screen capture does not) |
| `ffmpeg` | normalises + concatenates the segments |
| Pillow | draws the title/chapter/stat cards |
| Menlo | the typeface (macOS); swap `MONO` in `cards.py` and `Set FontFamily` in the tapes on other platforms |

`ffmpeg` here must decode/encode h264. Note the cards are drawn with Pillow rather than
ffmpeg's `drawtext` because that filter is absent from many stock ffmpeg builds.

Install Pillow into a throwaway venv — **never** into the repo's `.venv`, which exists to
prove `cap-evolve-core` installs with zero runtime dependencies:

```bash
python3 -m venv /tmp/vidvenv && /tmp/vidvenv/bin/pip install Pillow
```

## Build

```bash
cd scripts/demo-video
PATH="$PWD/../../.venv/bin:$PATH" vhs replay.tape      # ~30 s of TUI replay
PATH="$PWD/../../.venv/bin:$PATH" vhs parallel.tape    # live workers=1/4/8 measurement
/tmp/vidvenv/bin/python cards.py                       # title + chapter + stat cards
bash build.sh                                          # normalise, fade, concat
cp /tmp/video/cap-evolve-demo.mp4 ../../docs/assets/demo/
```

Output: 2560x1340, ~62 s, ~1.9 MB.

## If you change the numbers

`cards.py` restates the speedup figures that `parallel.tape` measures on camera. If you
re-record on different hardware, update the card to the numbers the footage actually
shows — a card that disagrees with its own footage is the one thing here worth failing a
review over.
