# cap-evolve site

The public-facing site at
[skillberry-ai.github.io/cap-evolve/](https://skillberry-ai.github.io/cap-evolve/).

Plain HTML + CSS. No framework, no build step, no JS.

## Structure

- `index.html` — home. Hero + quickstart + dashboard screenshot + results
  table + choose-your-path + doc tiles.
- `getting-started.html` — first-run walkthrough (adapted from
  `docs/GETTING_STARTED.md`).
- `results.html` — full benchmark detail (adapted from `docs/RESULTS.md`).
- `architecture.html` — pipeline + optimizer context (adapted from
  `docs/ARCHITECTURE.md`).
- `optimize-your-own.html` — adapter contract + two adoption paths (adapted
  from `docs/OPTIMIZE_YOUR_OWN.md`).
- `style.css` — one stylesheet for the whole site.
- `assets/` — images (logo thumbnail, dashboard screenshot).

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

- **Shared chrome (nav + footer) is duplicated across HTML files.** When you
  change the nav or footer, update every `*.html` in this directory. Five
  files today; grep for `class="nav"` and `class="footer"` to find them all.
  Consider a small build script if it grows past ~10 pages.
- **CSS cache-buster.** Every `<link rel="stylesheet" href="style.css?v=...">`
  in the HTML files carries a `?v=YYYYMMDD-N` query string. **Bump it when
  `style.css` changes** so returning visitors don't cache the old CSS.
- **Sub-pages summarize the source markdown docs, they do not replace them.**
  If you find yourself adding new content to a site page, consider whether it
  belongs in `docs/*.md` first (the site page then absorbs the change).
- **External links go to `github.com/skillberry-ai/cap-evolve/blob/main/...`**
  so they always resolve against the current default branch.

## Adding a new sub-page

1. Copy an existing sub-page (e.g. `getting-started.html`) as your template.
2. Update `<title>`, meta description, `<h1>`, and the `.active` marker in the
   nav.
3. Write the content inside `<main class="page-narrow doc">`.
4. Add a nav link in every HTML file (including `index.html`) so it's reachable.
5. Bump the CSS cache-buster in the new file's `<link>` if you also changed
   `style.css`.
