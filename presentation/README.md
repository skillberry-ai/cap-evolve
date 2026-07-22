# cap-evolve — Management review presentation

15-slide HTML deck for the cap-evolve management review.
Framework: [Reveal.js 5.1](https://revealjs.com) (vendored, offline-safe).

## Run it

```bash
# Simplest — open directly in a browser
open presentation/index.html         # macOS

# Or serve locally (recommended)
python3 -m http.server 8000 -d presentation
# → http://localhost:8000
```

## Drive on stage

- `→` / `←` — next / previous slide
- `S` — speaker view (opens a second window with notes, next slide, timer)
- `F` — fullscreen · `Esc` — overview mode
- `B` or `.` — pause (black screen)

## Export to PDF

```bash
open "http://localhost:8000/?print-pdf"
# Chrome only: File → Print → Save as PDF
# Layout: Landscape · Margins: None · Background graphics: ON
```

## Storyboard

**Part 1 · What cap-evolve is** — slides 1–4
**Part 2 · Where we stand (experiments &amp; results)** — slides 5–7
**Part 3 · Where we go from here** — slide 8 overview, slides 9–14 for the six sub-threads, slide 15 close.

| # | Slide | Part / Thread |
|---|---|---|
| 1  | Cover | — |
| 2  | What cap-evolve is (pitch + loop diagram + capability chips) | 1 |
| 3  | Why cap-evolve is different (6 differentiator tiles, 3×2) | 1 |
| 4  | Where cap-evolve stands today (status stats + recent shipping) | 1 |
| 5  | Results at a glance (three big numbers) | 2 |
| 6  | What actually changed (real edits) | 2 |
| 7  | External context (comparison + honesty caveats) | 2 |
| 8  | Six threads, one direction (roadmap overview) | 3 |
| 9  | Publication — benchmarks, baselines, prereqs, decisions | **3.1** |
| 10 | Working with Red Hat (Parsec PoC + head-to-head) | **3.2** |
| 11 | Skillberry Proxy &amp; Store *(placeholder — needs content)* | **3.3** |
| 12 | Memory / KB / LLM-wiki | **3.4** |
| 13 | Simulator from traces | **3.5** |
| 14 | Public research adoption (Arbor / EvoSkill / GEPA / SkillOps) | **3.6** |
| 15 | Three next steps + Q&amp;A | — |

## Placeholders — content the deck still needs

Every slide that needs more content has a visible `⚠` block or amber italic
line. Grep for `⚠` or `TO CONFIRM` in `index.html`. Current placeholders:

- **Cover** — presenter(s) &amp; date
- **Slide 3** — team &amp; attribution list
- **Slide 9 (3.1 Publication)** — venue, submission date, author list, compute budget, legal / IP review
- **Slide 11 (3.3 Skillberry)** — the entire slide content
- **Slide 12 (3.4 Memory / KB)** — KB shape, owners, first customer
- **Slide 13 (3.5 Simulator)** — named IBM contact + team + capacity
- **Slide 14 (3.6 Public research)** — "what to adopt" bullets, after paper read-through

## File layout

```
presentation/
├── README.md                        # this file
├── index.html                       # the deck — all slides inline
└── reveal/                          # vendored Reveal.js 5.1
    ├── dist/                        # kept via .gitignore negation rule
    └── plugin/
```
