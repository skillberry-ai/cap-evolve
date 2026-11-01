# cap-evolve dashboard — static export (τ²-bench airline, direct)

A self-contained, static snapshot of the cap-evolve dashboard for the direct run
`run_20261013_094928` of [`examples/tau2_sierra_airline`](../../../). It runs with no backend and no Python,
from any static file server.

## View it

```bash
cd examples/tau2_sierra_airline/direct/run/ui
python3 -m http.server 8000
# then open http://localhost:8000/#/runs/run_20261013_094928
```

The app uses hash routing, so it works from any subpath; drop the `ui/` folder on any static host.

## What's inside

```
ui/
  index.html   # the dashboard SPA (relative asset paths, hash router)
  assets/      # the built JS + CSS bundle (VITE_STATIC=1)
  data/        # pre-generated API responses, one JSON per endpoint
```

## What the export leaves out

- **Trajectories and rollouts**: omitted by the exporter by design.
- **τ²-bench's raw simulation files** (`native_sims/`) and the optimizer's per-task trajectory copies:
  left out to keep the export small; the run's scores, gate decisions, per-task results and
  candidate code are all here.
- **Host names and local paths**: replaced with `<gateway>` / removed.

## How it was generated

```bash
cd dashboard/frontend && VITE_STATIC=1 npx vite build --outDir /tmp/capui
python -m capevolve_dashboard.export_static --base .capevolve --run-id run_20261013_094928 --out <ui>/data
```

then the omissions above were applied to `data/`. See
[`docs/REPRODUCE_tau2_sierra_direct_blackbox.md`](../../../../../docs/REPRODUCE_tau2_sierra_direct_blackbox.md)
for the run's parameters and how to reproduce it.
