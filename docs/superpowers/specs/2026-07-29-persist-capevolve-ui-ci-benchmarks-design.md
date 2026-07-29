# Persist the CapEvolve UI for CI benchmark runs — Design

**Date:** 2026-07-29
**Status:** Approved design, pre-implementation

## Problem

`ci/benchmarks` (`.github/workflows/benchmarks.yml`) runs each benchmark/tier as a matrix job on
a self-hosted runner, producing a real CapEvolve run directory (`.capevolve/run_suite/` —
`events.jsonl`, `candidates/`, embedded git history, etc.). Today that run directory is
ephemeral: only the reduced `metrics.jsonl` / `report.md` / `runmeta.json` are uploaded as a GH
Actions artifact, and the raw run directory (everything the CapEvolve dashboard needs) is
discarded when the job ends. There is no way to open the dashboard for a specific CI run after
the fact — from the public benchmark history page
(`https://skillberry-ai.github.io/cap-evolve/benchmarks.html`) or otherwise.

## Goal

When a CI benchmark job completes (or is cancelled), persist a browsable snapshot of the
CapEvolve dashboard for that specific run, and link to it from `benchmarks.html`.

## Non-goals

- No changes to the live dashboard (`dashboard/`) itself beyond what already exists
  (`VITE_STATIC=1` build + `export_static.py` — both already shipped and demonstrated in
  `examples/tau2_airline/run_full/ui/`).
- No automatic retention/expiry. Snapshots are kept forever by default, matching
  `benchmark-history`'s existing "keep all" philosophy for records.
- No new server, database, or hosting provider — everything goes through the existing
  `benchmark-history` orphan branch and the existing GitHub Pages deployment.

## Design

### Data model — extend `benchmark-history`, don't add a new branch

Everything lives on the existing `benchmark-history` orphan branch, kept forever by default
(same as records today):

- `records/<run_id>__<tier>-<bench>.json` — unchanged, **plus a new `has_ui: bool` field** set
  at build time, so consumers know whether a snapshot exists without a separate manifest file.
- **New:** `runs/<run_id>__<tier>-<bench>/ui/` — a self-contained static CapEvolve dashboard
  export (shared Vite shell + that run's `data/*.json`), using the exact same slug as its record.

Kept-forever by default is a deliberate choice: it matches how `records/` already behaves, and
it avoids the complexity of squashing branch history (deleting a file in a new commit does not
reclaim the blob from git history, so any automatic pruning would need periodic history rewrites
to actually bound repo size — out of scope here; see "Manual pruning workflow" below instead).

### 1. Per-matrix `bench` job (self-hosted runner) — export the run

After `run_suite.sh` produces `<proj>/.capevolve/run_suite/`, add one best-effort step
(`if: always()`, so it still attempts to run when the job is cancelled) that runs:

```bash
python -m capevolve_dashboard.export_static \
  --base "<proj>/.capevolve" --run-id run_suite --out "$out_dir/ui/data"
```

guarded by a check that the run directory actually exists (a job that fails before producing any
run dir has nothing to export — skip silently, don't fail the job). This writes into the job's
*existing* `out_dir`, so it rides along in the artifact `actions/upload-artifact@v4` already
uploads — no new artifact is created.

Caveat: GitHub Actions gives a cancelled job only a short grace period before killing the
runner, so on cancellation this step is best-effort and may not always complete in time. This is
an accepted limitation, not a bug to fix here.

### 2. `aggregate` job (ubuntu-latest) — build the shell, assemble, push

The existing `aggregate` job (which already downloads artifacts and builds `records/*.json`)
gains:

1. **Build the static frontend shell once per aggregate run** (Node 22, mirroring `ci.yml`'s
   `actions/setup-node@v4` usage):
   ```bash
   cd dashboard/frontend && npm ci && VITE_STATIC=1 npx vite build --outDir "$RUNNER_TEMP/ui_shell"
   ```
   Vite's content-hashed filenames mean an unchanged frontend produces byte-identical output
   across runs, so this doesn't bloat the branch — git already dedupes identical blobs.
2. **Assemble each run's snapshot**: for every downloaded artifact that has a `ui/data/`
   directory, copy `$RUNNER_TEMP/ui_shell/*` + that artifact's `ui/data/` into
   `_hist/runs/<run_id>__<tier>-<bench>/ui/`.
3. **Set `has_ui: true`** on the corresponding record when its snapshot was assembled (`false`,
   or omitted, otherwise — e.g. historical records that predate this feature, or a job whose
   export step didn't run/failed).
4. **Push to `benchmark-history`** using the existing rebase-retry loop, unchanged — this stays
   an append-only branch; no squashing.

Add a `concurrency: group: benchmark-history-write` to the `aggregate` job (and to the manual
prune workflow below) so the two can never race writing to the same branch.

### 3. Manual prune workflow (new) — `.github/workflows/benchmark-history-prune.yml`

Since there's no automatic retention, a maintainer needs a deliberate way to reclaim space:

- Trigger: `workflow_dispatch` only, with input `days` (string, default `"30"`).
- `runs-on: ubuntu-latest`, `permissions: contents: write`, same `concurrency` group as above.
- Clones `benchmark-history`, computes a cutoff (`now - days`), and for every
  `records/<slug>.json` whose `date` is older than the cutoff: deletes the record file **and**
  its `runs/<slug>/ui/` directory (if present).
- Regenerates `benchmarks.json` / `meta.json` via the existing `record.py aggregate`, commits
  (message includes the cutoff and count deleted), and pushes with the same rebase-retry pattern
  used elsewhere.
- Logs what it deleted (slugs + dates) in the job summary so the action is auditable.
- This only removes files from the current tree (simple deletion commit) — it does not rewrite
  history to reclaim git object storage. That's an accepted limitation matching the "no
  automatic retention" decision; the point of this workflow is maintainer control over what's
  currently served, not minimizing `.git` size.

### 4. `pages.yml` — fold `benchmark-history`'s `runs/` into the Pages deploy

Unlike `benchmarks.json`/`meta.json` (fetched client-side at runtime, no redeploy needed), the
dashboard's `index.html`/JS must be served through GitHub Pages itself (raw.githubusercontent.com
serves `.html` as `text/plain`, which browsers won't render). So a Pages redeploy is required
whenever a new run's snapshot should become browsable.

- Add a `workflow_run: workflows: ["Benchmarks"], types: [completed]` trigger (in addition to the
  existing push-to-`main`-touching-`site/**` and `workflow_dispatch` triggers).
- The build job additionally checks out `benchmark-history` and copies its `runs/**` into the
  assembled artifact tree, alongside `site/**`, so the final deployed layout is:
  ```
  <pages-root>/                (from site/**)
  <pages-root>/benchmark-ui/runs/<slug>/ui/...   (from benchmark-history's runs/**)
  ```
- `upload-pages-artifact` uploads this combined tree; `deploy-pages` is otherwise unchanged.
- The existing `concurrency: group: "pages", cancel-in-progress: true` already serializes
  deploys, so an extra trigger source doesn't introduce new races.

### 5. `benchmarks.html` / `benchmarks.js` — the "Open UI" link

For every row whose record has `has_ui: true`, render an "Open UI" link/button pointing to:

```
./benchmark-ui/runs/<run_id>__<tier>-<bench>/ui/index.html#/runs/run_suite
```

(relative to the deployed Pages root, matching the path `pages.yml` assembles above). Rows
without `has_ui` (older records, or jobs where export failed/was skipped) simply show no link —
no broken-link handling needed since the field is authoritative at write time.

## Testing

- `record.py`: unit-test that `build` sets `has_ui` correctly (true when a matching `ui/data/`
  input is present, false/absent otherwise), and that `aggregate` passes `has_ui` through
  unchanged into `benchmarks.json`.
- `export_static.py` invocation in the `bench` job: exercise via the existing smoke-tier
  benchmark run (cheap, already part of normal CI usage) rather than a new dedicated test —
  confirm `ui/data/*.json` appears in the uploaded artifact and the assembled `runs/<slug>/ui/`
  renders correctly when opened locally.
- `benchmarks.js`: extend `site/benchmarks.fixture.json` with a `has_ui: true` example row and
  confirm the "Open UI" link renders with the expected href.
- New prune workflow: dry-run against a scratch copy of `benchmark-history` (or a throwaway test
  branch) before relying on it against the real branch; verify it deletes only records older
  than the cutoff and correctly removes their paired `runs/` directories.
- `pages.yml`: verify via `workflow_dispatch` that the combined artifact tree contains both
  `site/**` and `benchmark-ui/runs/**` before merging.
