# Demo video sources

Rebuilds `docs/assets/demo/cap-evolve-demo.mp4` — the README demo. Committed so the video
is reproducible rather than a one-off screen recording nobody can rebuild.

**Read [`STORYBOARD.md`](STORYBOARD.md) first.** It is the shot-by-shot treatment: what is
on screen, the exact copy, the exact voiceover, and the source of every number.
[`script.py`](script.py) is the machine-readable version of it and the single source of
truth — every duration, caption and narration line comes from there, so a card and its
voiceover cannot drift apart.

Output: **2560×1440, 88.8 s, 5.4 MB**, h264 + one mono AAC track (voiceover with a
generated music bed mixed under it), plus a `.srt` transcript. It is designed to be **fully
comprehensible with the sound off**, because that is how GitHub autoplays it — the narration
and the music add emphasis, never information.

## Nothing here is mocked

- The terminal segment is [`vhs`](https://github.com/charmbracelet/vhs) scripting a real
  terminal through `cap-evolve replay --demo`, which replays the committed
  `core/cap_evolve/demo_session/events.jsonl` through the **real** TUI renderer. The tape
  records a **112-column** terminal (`Set Width 2010`), not 144 — at 144 the home screen's
  ~87 columns of content sat hard left with 39 % of the frame dead on the right. See
  STORYBOARD.md shot 4 for the before/after measurements and why the text cannot be bigger.
- The dashboard segment is Playwright driving real Chromium against the **running**
  dashboard, over the committed run dir `examples/tau2_airline/run_agentopt_v4` — the most
  rigorous τ²-bench run here (`num_trials: 5`, 26/12/12 split, five candidates, five
  committed gate JSONs) and the one that ships with its own `events.jsonl`, so the shot is
  reproducible from a clean checkout. That run is a **null result**: `best_id = seed`, val
  0.5667 unchanged, sealed test 0.5000, every Δ = 0. The shot says so in the dashboard's own
  headline tiles (`BEST VAL 56.7% candidate seed`, `Δ VAL VS BASELINE 0.000`, `SEALED TEST
  50.0% · Δ 0.000`, `VERDICTS 5 candidates · 0 accept · 5 reject`) and in its voiceover.
  It claims **no spend**: that runner reports no per-call cost, so the dashboard prints
  `SPEND not reported` rather than a made-up `$0`. See STORYBOARD.md shot 6 for why the
  older `run_full` static export is *not* filmed.

**Footage carries no burned-in captions.** Both footage shots are shown clean; the old
lower-third bands are removed. Nothing was lost, because each shot's own output states its
caveat — and in the terminal shot's case the band used to sit *on top of* the renderer's own
"makes no benchmark claim" banner. Under `ANIMATIC=1` a small red corner badge is still
drawn on any stand-in segment.

> The demo session's *numbers* are hand-authored and make **no benchmark claim** — the
> renderer's own banner says so, on screen for the whole shot, and the voiceover says so.
> Real measured results come from `docs/RESULTS.md`.

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

Record the two footage segments (slow, so they are not part of `build.sh`):

```bash
vhs scripts/demo-video/replay.tape                                 # -> /tmp/video/replay.mp4

# the dashboard needs a server; the shipped cut films run_agentopt_v4.
# Kill strays first — a leftover on the fixed port has caused false failures.
pkill -f "cap-evolve dashboard"
.venv/bin/cap-evolve dashboard --base examples/tau2_airline --port 8791 --no-open &
/tmp/vidvenv/bin/python scripts/demo-video/dash.py \
    --live http://127.0.0.1:8791 --run run_agentopt_v4       # -> /tmp/video/dashboard.mp4
```

> **vhs framerate trap.** `Set Framerate 60` makes vhs stamp the mp4 60 fps while capturing
> nearer 25, so the file comes out *half as long as the tape* and plays ~2× too fast to
> read. `replay.tape` sets 30. If a re-recorded clip is suddenly too short for its
> `*_SEEK` window, check this first.

> **`replay.tape` runs *this* checkout's CLI.** It defines `cap-evolve() { python -m
> cap_evolve.cli "$@"; }` with `PYTHONPATH=core`, because a `cap-evolve` on `PATH` may well
> belong to a different clone. It also exports `COLORTERM=truecolor`, which is what unlocks
> the capybara mark in `core/cap_evolve/branding.py`.

Then assemble, in one command:

```bash
bash scripts/demo-video/build.sh
cp /tmp/video/cap-evolve-demo.mp4 docs/assets/demo/
```

`build.sh` draws the cards, synthesizes the voiceover, measures each line so no shot clips
or ends in silence, renders one clip per shot, concatenates, mixes the audio onto the same
timeline, and then **verifies** — video length vs planned, audio not overrunning video, no
voiceover line clipped by its own shot or by the end of the cut, the music bed at least as
long as the cut, and the 90 s budget. It **fails loudly** rather than quietly shipping a
short video:

- a missing footage segment is a fatal error naming the command that records it
- a music bed shorter than the cut is a fatal error
- a voiceover line that overruns its shot is a fatal error
- a card whose shot id no longer exists cannot leave a stale PNG behind — cards are wiped
  and re-rendered every build

### Which tabs the dashboard shot visits

`dash.py`'s `TABS` list is the tour: **Candidates** (lineage graph, 2.6 s) → **Gate**
(per-verdict table, 3.4 s) → **Tasks** (per-task val, 2.4 s). The tab set is generic across
algorithms — Overview, Candidates, Gate, Tasks, Cost, Logs, Agent rounds, Memory, Files —
so the old `Lineage` / `Git diffs` labels are gone.

**Cost is deliberately not filmed.** `run_agentopt_v4`'s runner reports no per-call cost, so
`cost.metered` is `false` and every ledger row is `$0.00`; the tab is honest but empty, and
3.4 s of zeros on camera says nothing. Its dwell went to Gate instead. If a metered run is
ever filmed, put `("Cost", 3600)` back — the reconciled attributed/unattributed ledger is
the best tab in the dashboard when there is spend to reconcile.

Tabs are clicked by `role=tab` **first**, exact name, then by visible text as a fallback.
Text-only matching silently clicked the *"4 candidates"* summary tile instead of the
Candidates tab and cost the shot two of its three beats — a missing tab prints
`(no 'X' here — skipping)` and shortens the shot rather than failing the build, so nothing
warns you.

## Useful knobs

| Env var | Default | What it does |
|---|---|---|
| `ANIMATIC=1` | off | allows stand-in footage, and stamps every stand-in shot with a red `STAND-IN FOOTAGE — NOT FINAL` line naming what it is blocked on |
| `TERM_SEEK` | 0.6 | where in `replay.mp4` the terminal shot starts — the tape opens on the home screen, so it plays from the top |
| `DASH_SEEK` | 1.6 | where in `dashboard.mp4` the dashboard shot starts |
| `OUTNAME` | `cap-evolve-demo.mp4` | output filename under `/tmp/video` |

## If you change the numbers

Don't hand-edit a figure onto a card. Every number is quoted from a named artifact and
carries a `src_note` in `script.py` saying which one — `docs/RESULTS.md` for four of the five
results rows, `site/assets/rh_swe_bench.png` for the RH-SWE-bench row. If a result changes,
change the artifact and then the `src_note`-bearing entry in `script.py`. **A card that
disagrees with its own source is the one thing here worth failing a review over.**

Note the cards no longer print a grey provenance footer (removed from shot 3 onward by
request), so `src_note` is now the *only* place the attribution lives. Keep it accurate.

## Why the cards look the way they do

- **Flat backgrounds, no dot grid, no gradient, no push-in on text cards.** All three read
  as depth to the eye and as high-frequency noise to x264: the first cut of this video was
  16 MB, and 12 MB of that was a 3% zoom on still text. The animated opener and the live
  footage are where movement earns its bitrate.
- **Music is generated, never downloaded.** [`music.py`](music.py) synthesises the bed with
  the stdlib `wave` module: a slow four-chord pad (Am–F–G/C–Em, one chord per 8 s,
  raised-cosine cross-fades, sine plus two quiet harmonics, a ~0.12 Hz tremolo, no
  percussion). Nothing is fetched, so there is nothing to license or attribute, and the same
  chord table always produces the same wav. `assets.py` renders it to the exact runtime and
  caches on frame count; `build.sh` mixes it under the narration at `script.MUSIC_DB`
  (**-20 dB**) with `MUSIC_FADE_IN` 2.5 s and `MUSIC_FADE_OUT` 3.5 s. Run
  `music.py --check` for its self-check (length, no clipping, not silent, chords distinct).
