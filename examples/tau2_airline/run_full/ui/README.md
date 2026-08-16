# cap-evolve dashboard — static export (tau2-airline `run_full`)

A **fully self-contained, static** snapshot of the cap-evolve React dashboard,
populated with the completed **10-iteration tau2-airline** run (`run_full`). It
runs on **any computer with no backend and no Python** — just a static file
server. This is the real SPA, reading pre-generated JSON from `./data/` instead of
the FastAPI backend.

The dashboard renders **nine** tabs for this run:

    Overview · Candidates · Gate · Tasks · Cost · Logs · Diffs · Memory · Files

(The older `Phases`, `Lineage`, `Iterations`, `Git diffs` and `Insights` tabs no
longer exist: the tab set is algorithm-agnostic now, phases live at the bottom of
Overview and the lineage tree at the top of Candidates.)

> **What this export cannot show, and why.** It ships no `events.jsonl` and no
> `state.json`, so the run's **status**, **algorithm** and **split sizes** are
> genuinely absent from the payload — the header says "not recorded" rather than
> guessing, and the Logs tab is empty. Everything else is real: the Gate table,
> the per-task heatmap and the diffs are rebuilt from the candidate graph, which
> the export does carry. **Trajectories/rollouts are omitted by design**, so that
> tab is not offered at all.

## View it

Any static server works. The simplest:

```bash
cd examples/tau2_airline/run_full/ui
python3 -m http.server 8000
# then open http://localhost:8000
```

The app uses **hash routing** (`/#/runs/run_full`), so client-side navigation
works from any subpath with no server rewrites. Drop the whole `ui/` folder on
**GitHub Pages**, Netlify, S3, or any static host and it just works — all asset
and data references are relative.

## What's inside

```
ui/
  index.html            # the SPA entry (relative asset paths, hash router)
  assets/               # built JS + CSS bundle (Vite, VITE_STATIC=1 build)
  favicon.png
  data/                 # pre-generated API responses (one JSON per endpoint)
  README.md
```

`data/` filenames are a deterministic slug of each `/api/*` path+query (matching
the frontend's `staticSlug()`), e.g. `runs_run_full.json` (run detail with all 10
iterations), `runs_run_full_git_log.json`, `runs_run_full_diff_cand_0007.json`,
`runs_run_full_memory.json`, `runs_run_full_git_diff_from_<sha>_1_to_<sha>.json`.

## How it was generated

1. Build the SPA in static mode (relative base, hash router). Build to a **temp**
   dir and copy `index.html` + `assets/` in, so `data/` and the icons survive:
   ```bash
   cd dashboard/frontend && VITE_STATIC=1 npx vite build --outDir /tmp/capui
   cd - && cp /tmp/capui/index.html examples/tau2_airline/run_full/ui/
   rm -f examples/tau2_airline/run_full/ui/assets/index-*
   cp /tmp/capui/assets/* examples/tau2_airline/run_full/ui/assets/
   ```
   **Rebuild this bundle whenever the frontend changes.** It is a committed build
   artifact, so it goes stale silently: it once shipped a chart in which a
   *rejected* candidate raised the cumulative-best stair, months after the source
   was fixed. `scripts/tools/shoot_dashboard.py` screenshots whatever is in
   `assets/`, not whatever is in `src/`.
2. Export the run's JSON with the backend reducers (same shapes as live):
   ```bash
   python -m capevolve_dashboard.export_static \
     --base <.capevolve> --run-id run_full --out <ui>/data
   ```

The normal **live** dashboard is unchanged: static mode is opt-in via the
`VITE_STATIC=1` build flag (or a runtime `window.__CAPEVOLVE_STATIC__` global).
