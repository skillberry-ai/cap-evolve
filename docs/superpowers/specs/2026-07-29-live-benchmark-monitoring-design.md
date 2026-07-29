# Live benchmark run monitoring — design

## Goal

From `site/benchmarks.html`, let a visitor see which `ci/benchmarks` CI runs are
currently in progress (there may be several, across multiple self-hosted
runners), and open the actual CapEvolve dashboard UI to watch one execute —
with at most a few minutes of lag, no true real-time (SSE) streaming, and no
new public network exposure of the self-hosted runner.

This builds directly on the per-run CapEvolve UI snapshot work already merged
in PR #176 (`benchmark-history` branch, `runs/<run_id>__<tier>-<bench>/`,
`export_static.py`, the Vite static shell build). It does not change anything
about how *finished* runs are recorded or viewed.

## Non-goals

- True sub-minute / SSE live streaming. Would require exposing the self-hosted
  VPC runner's dashboard server to the public internet via a tunnel — ruled
  out for this pass on security/ops grounds. A periodic snapshot (default
  every 5 minutes) is the accepted tradeoff.
- Auto-refreshing the SPA tab while a live run is open. The viewer reloads the
  tab to see newer data. Possible future enhancement, not built here.
- Any change to how finished-run history/records/pruning work (PR #176).
- Retention/cleanup automation for the new `live/` directory beyond what falls
  out naturally from the architecture (see "Orphaned entries" below).

## Architecture

Three independent pieces:

### 1. Detecting in-progress runs — client-side, GitHub Actions API

`benchmarks.js` calls GitHub's public REST API directly from the browser,
with no new backend or CI-side status reporting:

- `GET /repos/skillberry-ai/cap-evolve/actions/workflows/benchmarks.yml/runs?status=in_progress`
- For each returned run, `GET /repos/skillberry-ai/cap-evolve/actions/runs/{id}/jobs`
  — job `name` is already `"<tier> / <bench>"` (set by the `bench` job's
  `name: ${{ matrix.tier }} / ${{ matrix.bench }}`), so no new metadata is
  needed. Filter to jobs matching `/^(smoke|full) \/ (tau2|swebench|skillsbench)$/`
  and `status == "in_progress"` (this also excludes the `aggregate` job, whose
  name doesn't match).

Rendered as a "Running now" panel above the existing table, refreshed on a
client-side timer (every 60s) independent of the existing filter-driven
`render()`. No auth token is embedded (would leak client-side) — unauthenticated
GitHub API access is capped at 60 requests/hour per source IP, which is ample
for a lightly-trafficked internal page on a 60s refresh.

### 2. Periodic snapshot push — CI side, self-hosted runner

New steps in the `bench` job of `.github/workflows/benchmarks.yml`:

- **Before** "Run suite": background a polling loop (new script,
  `ci/benchmarks/lib/live_push.sh`) that every 5 minutes (hardcoded constant,
  not a workflow input — YAGNI), if `events.jsonl` exists under the
  in-progress run's `.capevolve/run_suite` dir, runs the *existing*
  `export_static.py` (pure Python, already available via the cached
  `$CAPEVOLVE_PY` venv — no Node/Vite needed on this runner) into a temp dir,
  then clones/copies/commits/pushes that data to
  `live/<run_id>__<tier>-<bench>/data/` on the `benchmark-history` branch,
  **overwriting in place** — no history of intermediate snapshots is kept,
  only ever the latest. `<run_id>` is `github.run_id`; `<tier>-<bench>` is the
  same slug format the `aggregate` job already uses for `runs/<slug>/`
  (e.g. `smoke-tau2`), so both directories are keyed consistently.
- **After** "Run suite" (`if: always()`): kill the poller process, then push
  one more time to delete that `live/<slug>/` entry (best-effort) — the run is
  no longer "live" regardless of outcome (success/failure/cancelled); the
  permanent snapshot lands separately, moments later, via the existing
  `aggregate` job's `runs/<slug>/` write.
- The `bench` job's permissions gain `contents: write` (currently `read`),
  matching what `aggregate` and the prune workflow already have, scoped to
  this job only.
- The push logic is its own independent clone→copy→commit→push retry loop
  (matching the existing convention: `aggregate` and the prune workflow each
  already have their own independent copy of this pattern; this is a third
  independent copy, not a new instance of duplication that needs fixing).

### 3. Viewing it — the same SPA the finished runs use

Rather than copying the compiled shell (JS/CSS bundle) into `benchmark-history`
per run (as the finished-run path does), the live path uses one shell,
built once per Pages deploy, with the data location parameterized at
request time:

- `.github/workflows/pages.yml`'s `build` job builds the SPA shell once
  per deploy: `VITE_STATIC=1 npx vite build --outDir site/dashboard-ui`
  (same pattern `aggregate` already uses for the finished-run shell). This
  output is never committed to git — it's a normal build artifact produced
  fresh on every Pages deploy.
- `dashboard/frontend/src/lib/api.ts`: `DATA_BASE` changes from a
  module-level constant (`'data'`) to a function read lazily inside
  `getJSON()`, checking `window.__CAPEVOLVE_DATA_BASE__` first. This must be
  read lazily (inside the function, not at module-eval time) because
  `main.tsx` sets that window global *after* `api.ts` has already been
  imported and evaluated — a module-level `const` would capture the default
  before the override is set.
- `dashboard/frontend/src/main.tsx`: before mounting, reads a `?dataBase=`
  query param from `window.location.search` and, if present, sets
  `window.__CAPEVOLVE_DATA_BASE__` to it.
- The "Watch live" link/button (next to each "Running now" entry) opens, in a
  new tab:
  `dashboard-ui/index.html?dataBase=<encoded raw.githubusercontent.com URL for live/<slug>/data>#/runs/run_suite`
  — the already-deployed shell fetches its JSON directly from
  `benchmark-history` via `fetch()` (the same cross-origin pattern
  `benchmarks.js` already relies on for `benchmarks.json`/`meta.json`; GitHub's
  raw content already sends permissive CORS headers).
- **No Pages redeploy is needed while a run is in progress.** The shell is
  generic and doesn't change per run; only the query param changes, and the
  data fetch happens client-side at view time. This sidesteps the fact that
  `pages.yml` today only redeploys when the whole `Benchmarks` workflow run
  *completes*, which would otherwise be too late for a live view.

## Data flow summary

```
bench job (self-hosted runner)
  └─ every 5 min: export_static.py → live/<run_id>__<tier>-<bench>/data/  (overwritten, benchmark-history branch)
  └─ on completion (always()): delete that live/<slug>/ entry

benchmarks.html (visitor's browser)
  ├─ GitHub Actions API → which tier/bench jobs are in_progress right now
  └─ "Watch live" → dashboard-ui/index.html?dataBase=.../live/<slug>/data
                       └─ fetches JSON straight from benchmark-history, renders the full SPA
```

## Edge cases

- **No live snapshot yet** (run just started, first 5-min poll hasn't landed):
  the SPA's data fetch 404s. Relying on the SPA's existing error handling for
  now; revisit with a friendlier message only if manual testing shows a bad
  UX.
- **Orphaned `live/` entries** (hard runner crash, cleanup step never runs):
  harmless. "What's running" is derived from the GitHub Actions API, not from
  `live/`'s existence, so an orphaned entry is simply never linked to. It sits
  unused until a future run overwrites the same slug, or until the existing
  manual prune workflow (from PR #176) sweeps it — no new cleanup automation
  needed for this.
- **Push races** across multiple concurrent bench jobs (up to 6: `{smoke,full}
  × {tau2,swebench,skillsbench}`, each pushing independently every 5 min):
  handled by the same retry loop already proven in `aggregate`/the prune
  workflow (re-clone, re-apply, retry on push rejection).
- **Rate limits:** unauthenticated GitHub API, 60 req/hr/IP — acceptable for
  this page's traffic and 60s client refresh.

## Testing

- No new Python logic — `export_static.py` is reused unchanged, so no new
  pytest coverage needed there.
- `api.ts`/`main.tsx`: a small vitest case verifying the `dataBase` override
  is honored by `getJSON()`.
- YAML validation (`yaml.safe_load`) for the modified `benchmarks.yml` and
  `pages.yml`.
- The live path cannot be fully exercised without a real in-progress run on
  the VPC runner — same documented limitation as PR #176.
