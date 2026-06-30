# cap-evolve dashboard — static export (tau2-airline `run_full`)

A **fully self-contained, static** snapshot of the cap-evolve React dashboard,
populated with the completed **10-iteration tau2-airline** run (`run_full`). It
runs on **any computer with no backend and no Python** — just a static file
server. This is the real SPA (every page/tab: Overview/KPIs, Cost, Phases,
Lineage, Iterations + git diffs, Memory, Files, Insights), reading pre-generated
JSON from `./data/` instead of the FastAPI backend.

> **Trajectories / rollouts are omitted** from this export by design. The
> Trajectories tab renders gracefully empty ("No rollouts"), and Insights shows
> "No tool calls observed in sampled rollouts".

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

1. Build the SPA in static mode (relative base, hash router):
   ```bash
   cd dashboard/frontend && VITE_STATIC=1 npx vite build --outDir <ui>
   ```
2. Export the run's JSON with the backend reducers (same shapes as live):
   ```bash
   python -m capevolve_dashboard.export_static \
     --base <.capevolve> --run-id run_full --out <ui>/data
   ```

The normal **live** dashboard is unchanged: static mode is opt-in via the
`VITE_STATIC=1` build flag (or a runtime `window.__CAPEVOLVE_STATIC__` global).
