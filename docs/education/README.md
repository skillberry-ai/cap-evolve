# cap-evolve onboarding course

An onboarding course for a software engineer who joins the cap-evolve team. The listener knows AI, agents
and optimization well, but does not know cap-evolve. The course has 8 chapters of about 20 minutes each,
about 2 hours 40 minutes in total. It starts with the motivation and goes deep into the code.

The slides are in English. Every slide has speaker notes in English and in Hebrew.

## Start here

Open the course home page. It lists all chapters and has buttons to present each one.

From the repo root:

```bash
open -a "Google Chrome" docs/education/index.html     # macOS
xdg-open docs/education/index.html                    # Linux
```

Or open `docs/education/index.html` from your file browser. No server is needed.

On the home page:

1. Pick the notes language: **English** or **עברית**.
2. On a chapter, click one of:
   - **Present with notes**: the slides with the notes panel under them.
   - **Slides only**: for the projector. Press `P` in it to open the presenter window.
   - **Handout**: every slide with its notes, to read or print to PDF.

## Chapters

| # | Deck | Topic | Slides |
|---|---|---|---|
| 1 | [`01-why-cap-evolve.html`](01-why-cap-evolve.html) | Motivation, the idea, the loop, results, demo, course map | 21 |
| 2 | [`02-vocabulary-and-config.html`](02-vocabulary-and-config.html) | Terms, user-facing objects, `capevolve.yaml`, the CLI | 21 |
| 3 | [`03-repo-map-and-build.html`](03-repo-map-and-build.html) | Folders, core package, module map, skills registry, dashboard build, CI | 19 |
| 4 | [`04-object-model.html`](04-object-model.html) | Dataclasses, adapter contract, run dir, events, lineage, cache, memory | 22 |
| 5 | [`05-anatomy-of-a-run.html`](05-anatomy-of-a-run.html) | Execution flow, one iteration, processes and threads | 22 |
| 6 | [`06-honest-evaluation.html`](06-honest-evaluation.html) | Splits, trials, pass^k, the paired gate, the sealed test | 22 |
| 7 | [`07-algorithms-optimizers-skills.html`](07-algorithms-optimizers-skills.html) | Skill library, algorithms, optimizer backends, hosts, extending | 19 |
| 8 | [`08-debug-observe-test.html`](08-debug-observe-test.html) | Debugging, observability, tests, CI, first-week plan | 22 |

## Ways to present

### One screen: notes under the slide

Open a deck with `?notes`. Add `&lang=he` for Hebrew notes.

```text
file://<repo>/docs/education/01-why-cap-evolve.html?notes
file://<repo>/docs/education/01-why-cap-evolve.html?notes&lang=he
```

`<repo>` is the absolute path of your cap-evolve checkout. The home page shows the full path for your machine.

Press `N` to hide or show the notes and `L` to switch between English and Hebrew.

### Two screens: projector and presenter window

1. Open the deck without `?notes`, move that window to the projector, and press `F` for full screen.
2. Press `P`. A presenter window opens with the current slide, the next slide, the notes and a timer.
3. Keep the presenter window on your own screen. Moving in either window moves both.

If the browser blocks the pop-up, allow pop-ups for the page and press `P` again.

### Reading copy

Add `?handout` to a deck's address, or press `D` inside a deck. It shows every slide with its notes.
Print it to PDF (`⌘P` → Save as PDF) to get a reading copy.

```text
file://<repo>/docs/education/06-honest-evaluation.html?handout&lang=he
```

### Timing

Each slide's notes start with a time marker such as `[4:00–5:30]`. Every chapter adds up to about 20 minutes.
The presenter window shows a timer and the target length.

## Keyboard

| Key | Action |
|---|---|
| `→` `Space` / `←` | Next / previous step or slide |
| `Home` / `End` | First / last slide |
| `N` | Show or hide the speaker notes panel |
| `L` | Switch the notes language: English / Hebrew |
| `P` | Presenter window: current and next slide, notes, timer |
| `O` | Overview of all slides; click one to jump to it |
| `D` | Handout: all slides with notes |
| `F` | Full screen |
| `?` / `Esc` | Keyboard help / close overview, handout or help |

## URL options

| Option | Effect |
|---|---|
| `?notes` | Open with the notes panel showing |
| `?lang=he` | Start with Hebrew notes (`en` is the default) |
| `?handout` | Open the handout |
| `#/N` | Jump to slide N, for example `05-anatomy-of-a-run.html?notes#/9` |

Combine options with `&`, for example `?notes&lang=he#/5`.

The decks work offline from the local files. With no network, the fonts fall back to system fonts.

## Files

```text
docs/education/
├── index.html            course home page: pick a chapter and a notes language
├── README.md             this file
├── 01-…html … 08-…html   the chapter decks
├── _template.html        starting point for a new deck
├── assets/deck.css       shared slide styles (1280×720 canvas, cap-evolve palette)
├── assets/deck.js        shared slide engine (keys, notes, presenter, handout, layout check)
└── tools/check.sh        layout check: overflow, clipping and missing notes, per slide
```

## Editing a deck

Each slide is one `<section class="slide">` with two speaker-note blocks:

```html
<section class="slide">
  <h2>Slide title</h2>
  … content …
  <aside class="notes" lang="en"><p><span class="time">[3:00–4:30]</span> English notes.</p></aside>
  <aside class="notes" lang="he"><p><span class="time">[3:00–4:30]</span> הערות בעברית.</p></aside>
</section>
```

Add `class="fragment"` to an element to show it on the next key press. The layout classes (`card`, `term`,
`flow`, `tree`, `callout`, `grid-3`, `svg.diagram` and more) are listed in `assets/deck.css`.

After an edit, run the layout check. Every slide must print `ok`:

```bash
docs/education/tools/check.sh 05-anatomy-of-a-run.html
docs/education/tools/check.sh --shots 05-anatomy-of-a-run.html   # also writes PNGs to /tmp/edu-shots/
```

The check needs Google Chrome. Set `CHROME=/path/to/chrome` if Chrome is not in the default macOS location.

## Keeping the course current

The content describes the `main` branch as of 2026-11-16. File names, function names, spec keys and CLI
options on the slides are taken from the code. When one of them changes, search the decks for the old name
and update the slide and both note blocks.
