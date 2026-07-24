# cap-evolve site

The public-facing site at
[skillberry-ai.github.io/cap-evolve/](https://skillberry-ai.github.io/cap-evolve/).

Hand-written HTML + CSS with a tiny sprinkle of vanilla JS (theme toggle,
scroll-reveal, TOC scrollspy, code copy buttons). **No framework, no build step** —
the `site/` directory is shipped verbatim. Dark-first, with a light-mode toggle.

## Structure

- `index.html` — home. Hero + quickstart + how-it-works + before→after + real
  dashboard screenshots + why + results + doc tiles.
- `getting-started.html` — first-run walkthrough, zero-API `toy_calc` (from `docs/GETTING_STARTED.md`).
- `run-end-to-end.html` — step-by-step run on a real benchmark, τ²-bench airline
  (from `docs/REPRODUCE_tau2.md` + `examples/tau2_airline/DEMO.md`).
- `results.html` — full benchmark detail (from `docs/RESULTS.md`); includes an inline SVG dumbbell chart.
- `benchmarks.html` — live CI benchmark-run history; rendered by `benchmarks.js` from a JSON feed.
- `architecture.html` — pipeline + optimizer context (from `docs/ARCHITECTURE.md`); includes an inline SVG pipeline diagram.
- `optimize-your-own.html` — adapter contract + two adoption paths (from `docs/OPTIMIZE_YOUR_OWN.md`).
- `agent-orchestration.html` — deterministic vs agent mode (from `docs/AGENT_ORCHESTRATION.md`).
- `adapter-templates.html` — config-only adapter templates (from `docs/ADAPTER_TEMPLATES.md`).
- `style.css` — one stylesheet (design tokens for dark + light, all components).
- `js/site.js` — theme toggle, scroll-reveal (IntersectionObserver), TOC scrollspy, copy buttons. Progressive enhancement; content is fully readable without it.
- `benchmarks.js` — fetches + renders the benchmark-run history table.
- `assets/` — logo/mascot, favicon, and real dashboard screenshots (`dash-*.png`).

## Design system (quick reference)

- **Theme:** dark by default; an inline `<head>` script applies `data-theme` pre-paint
  (no FOUC) and reads an explicit choice from `localStorage`. The nav `.theme-toggle`
  flips and persists it. Tokens + light overrides live at the top of `style.css`.
- **Fonts:** Fira Sans (UI) + Fira Code (mono/numbers), from Google Fonts — matches the dashboard.
- **Palette:** blue `#3b82f6` primary, amber `#f59e0b` "champion" accent, green/red for accept/reject — matches the dashboard.
- **Motion:** add class `reveal` to a block to fade-up on scroll. All motion is disabled under `prefers-reduced-motion`.
- **Components:** `.btn`/`.btn-primary`/`.btn-ghost`, `.eyebrow`, `.pill`/`.badge`, `.card`/`.card-grid`, `.diff-tile(s)`, `.stat(-strip)`, `.beforeafter`, `.steps`/`.step`, `.shot`/`.shot-grid`, `.callout`(+`-accent`/`-warn`), `.table`/`.table-hero`, `.with-toc`+`.toc`. See `index.html` and `run-end-to-end.html` for usage.

## Preview locally

```bash
scripts/preview-site.sh          # serves at http://localhost:8080
PORT=9090 scripts/preview-site.sh
```

## Publishing

Auto-deployed by `.github/workflows/pages.yml` on push to `main` when any file
under `site/` (or the workflow itself) changes. Ships the `site/` directory
verbatim.

First-time setup (once per repo, done in GitHub Settings):

1. Repo settings → Pages → *Source*: **GitHub Actions**.
2. Push a commit that touches `site/`. The workflow runs and prints the live
   URL (also visible under Settings → Pages).

## Editing conventions

- **Shared chrome (nav + footer + the `<head>` theme/font block) is duplicated
  across HTML files.** When you change any of it, update every `*.html` here.
  Grep for `class="nav"` and `class="footer"` to find them all.
- **CSS/JS cache-buster.** Every `style.css?v=...` and `js/site.js?v=...` link
  carries a `?v=YYYYMMDD` query. **Bump it when the file changes** so returning
  visitors don't cache the old asset.
- **Sub-pages summarize the source markdown docs, they do not replace them.**
- **Honest numbers.** This project's premise is honest evaluation. Label every
  figure `fit metric` (no holdout) or `held-out`; never present a reported-but-
  not-yet-committed number as artifact-backed. Cross-check against `docs/RESULTS.md`
  and the committed run artifacts before editing a results figure.
- **External links go to `github.com/skillberry-ai/cap-evolve/blob/main/...`.**

## Adding a new sub-page

1. Copy `getting-started.html` as your template (it carries the canonical chrome).
2. Update `<title>`, meta description, canonical/OG, `<h1>`, and the `.active` marker in the nav.
3. Write the content inside `<main class="page-narrow doc">` (or `page doc` + `.with-toc` for long pages).
4. Add a nav/footer link where appropriate, and a `sitemap.xml` entry.
5. Bump the cache-buster if you also changed `style.css`/`site.js`.
