# Demo video sources

Rebuilds `docs/assets/demo/cap-evolve-demo.mp4` — the README demo. Committed so the video
is reproducible rather than a one-off screen recording nobody can rebuild.

**Read [`STORYBOARD.md`](STORYBOARD.md) first.** It is the shot-by-shot treatment: what is
on screen, the exact copy, the exact voiceover, and the source of every number.
[`script.py`](script.py) is the machine-readable version of it and the single source of
truth — every duration, caption and narration line comes from there, so a card and its
voiceover cannot drift apart.

Output: **2560×1440, 89.5 s, 5.2 MB**, h264 + one mono AAC voiceover track, plus a `.srt`
transcript. It is designed to be **fully comprehensible with the sound off**, because that
is how GitHub autoplays it — the narration adds emphasis, never information.

## Nothing here is mocked

- The terminal segment is [`vhs`](https://github.com/charmbracelet/vhs) scripting a real
  terminal through `cap-evolve replay --demo`, which replays the committed
  `core/cap_evolve/demo_session/events.jsonl` through the **real** TUI renderer.
- The dashboard segment is Playwright driving real Chromium against the **running**
  dashboard, over the committed run dir `examples/tau2_airline/run_agentopt` — a real
  $12.98 τ²-bench run. That run is a **null result** (four candidates, none accepted), and
  the shot says so in its lower-third and its voiceover. See STORYBOARD.md shot 6 for why
  the older `run_full` static export is *not* filmed.
- The parallel segment is `par_demo.py` measured live, on camera.

> The demo session's *numbers* are hand-authored and make **no benchmark claim** — the
> lower-third says so, the renderer's own banner says so, and the voiceover says so. Real
> measured results come from `docs/RESULTS.md`. The speedup is the one figure measured live.

## Requirements

| Tool | Why |
|---|---|
| [`vhs`](https://github.com/charmbracelet/vhs) | renders a scripted terminal to mp4 with a real font, so text stays crisp at 1440p (a screen capture does not) |
| `ffmpeg` | normalises, fades, concatenates, and mixes the voiceover |
| Pillow | draws every card — this build of ffmpeg has no `drawtext` and no `subtitles` filter |
| Playwright + Chromium | records the dashboard as *video*, and rasterises the two SVG logos |
| `say` | macOS built-in TTS for the voiceover (voice `Samantha`, rate 168) |
| Menlo + SF Pro | the type system — mono for data and code (matching the terminal footage), SF Pro for headlines. Swap `MONO`/`SANS` in `script.py` on other platforms. |

Install the Python bits into a throwaway venv — **never** into the repo's `.venv`, which
exists to prove `cap-evolve-core` installs with zero runtime dependencies, and a test
asserts it:

```bash
python3 -m venv /tmp/vidvenv
/tmp/vidvenv/bin/pip install Pillow playwright
```

## Build

Record the three footage segments (slow, so they are not part of `build.sh`):

```bash
PATH="$PWD/.venv/bin:$PATH" vhs scripts/demo-video/replay.tape     # -> /tmp/video/replay.mp4
PATH="$PWD/.venv/bin:$PATH" vhs scripts/demo-video/parallel.tape   # -> parallel.mp4 (+ par_results.json)

# the dashboard needs a server; the shipped cut films run_agentopt
.venv/bin/cap-evolve dashboard --base examples/tau2_airline --port 8791 --no-open &
/tmp/vidvenv/bin/python scripts/demo-video/dash.py \
    --live http://127.0.0.1:8791 --run run_agentopt          # -> /tmp/video/dashboard.mp4
```

> **vhs framerate trap.** `Set Framerate 60` makes vhs stamp the mp4 60 fps while capturing
> nearer 25, so the file comes out *half as long as the tape* and plays ~2× too fast to
> read. Both tapes are 30 or default. If a re-recorded clip is suddenly too short for its
> `*_SEEK` window, check this first.

Then assemble, in one command:

```bash
bash scripts/demo-video/build.sh
cp /tmp/video/cap-evolve-demo.mp4 /tmp/video/cap-evolve-demo.srt docs/assets/demo/
```

`build.sh` draws the cards, synthesizes the voiceover, measures each line so no shot clips
or ends in silence, renders one clip per shot, concatenates, mixes the audio onto the same
timeline, and then **verifies** — video length vs planned, audio not overrunning video, and
the 90 s budget. It **fails loudly** rather than quietly shipping a short video:

- a missing footage segment is a fatal error naming the command that records it
- `par_results.json` newer than `parallel.mp4` is a fatal error, because it would mean the
  speedup card is quoting a different run than the footage shows
- a `SplitResult` divergence reported by `par_demo.py` is a fatal error
- a card whose shot id no longer exists cannot leave a stale PNG behind — cards are wiped
  and re-rendered every build

### Which tabs the dashboard shot visits

`dash.py`'s `TABS` list is the tour: **Candidates** (lineage graph) → **Gate** (per-verdict
table) → **Cost** (reconciled ledger). The tab set is now generic across algorithms —
Overview, Candidates, Gate, Tasks, Cost, Logs, Diffs, Trajectories, Memory, Files — so the
old `Lineage` / `Git diffs` labels are gone.

Tabs are clicked by `role=tab` **first**, exact name, then by visible text as a fallback.
Text-only matching silently clicked the *"4 candidates"* summary tile instead of the
Candidates tab and cost the shot two of its three beats — a missing tab prints
`(no 'X' here — skipping)` and shortens the shot rather than failing the build, so nothing
warns you.

## Useful knobs

| Env var | Default | What it does |
|---|---|---|
| `ANIMATIC=1` | off | allows stand-in footage, and stamps every stand-in shot with a red `STAND-IN FOOTAGE — NOT FINAL` line naming what it is blocked on |
| `TERM_SEEK` | 7.7 | where in `replay.mp4` the terminal shot starts — lands the window on the finished lineage |
| `DASH_SEEK` | 1.6 | where in `dashboard.mp4` the dashboard shot starts |
| `PAR_SEEK` | 13.5 | where in `parallel.mp4` `workers=8` lands and the identical-SplitResult line prints |
| `OUTNAME` | `cap-evolve-demo.mp4` | output filename under `/tmp/video` |

## If you change the numbers

Don't hand-edit a figure onto a card. The speedup card is *generated* from the measurement
the camera filmed; every other number is quoted from `docs/RESULTS.md` and carries a
`src_note` in `script.py` saying so. If a result changes, change `docs/RESULTS.md` and then
the `src_note`-bearing entry in `script.py`. **A card that disagrees with its own footage is
the one thing here worth failing a review over.**

## Why the cards look the way they do

- **Flat backgrounds, no dot grid, no gradient, no push-in on text cards.** All three read
  as depth to the eye and as high-frequency noise to x264: the first cut of this video was
  16 MB, and 12 MB of that was a 3% zoom on still text. The animated opener and the live
  footage are where movement earns its bitrate.
- **No music.** No royalty-free bed could be sourced without fetching third-party audio, and
  a synthesized one sounded worse than silence. Shipped without; the voiceover carries the
  audio track. If a cleanly-licensed bed turns up, mix it in `build.sh` step 5 at about
  −26 dB.
