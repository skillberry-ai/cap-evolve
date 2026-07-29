# Live benchmark run monitoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a visitor on `site/benchmarks.html` see which `ci/benchmarks` CI jobs are currently in progress and open the real CapEvolve dashboard SPA to watch one execute, with at most a few minutes of lag.

**Architecture:** A new backgrounded poller script (`ci/benchmarks/lib/live_push.sh`) runs inside each `bench` matrix job on the self-hosted runner, exporting the in-progress run's static dashboard data every 5 minutes and overwriting `live/<run_id>__<tier>-<bench>/data/` on the `benchmark-history` branch (never appending — always the latest only), then deleting that entry when the job ends. `benchmarks.html` polls the GitHub Actions REST API client-side (unauthenticated) to know which `<tier>/<bench>` jobs are `in_progress`, and links each to one generically-built, already-deployed SPA shell (`site/dashboard-ui/`, built once per Pages deploy) with the live data location passed as a `?dataBase=` query param — so no Pages redeploy is needed while a run is in progress.

**Tech Stack:** Bash (CI script), GitHub Actions YAML, TypeScript/React (existing Vite SPA), vanilla JS (existing `site/benchmarks.js`), Python (`export_static.py`, reused unchanged).

## Global Constraints

- The 5-minute poll interval is a hardcoded constant in `live_push.sh` (`INTERVAL=300`), not a workflow input — YAGNI, per spec.
- `live/<slug_dir>/data/` is always **overwritten in place**; never append or keep history of intermediate snapshots.
- No auth token is ever embedded in `site/benchmarks.js` (client-side, public page) — GitHub API calls there are unauthenticated.
- `export_static.py` is reused **unchanged** — no new Python logic.
- The live-push clone→copy→commit→push retry loop in `live_push.sh` is its **own independent copy**, not shared/extracted with the `aggregate` job's or the prune workflow's existing copies of the same pattern (explicit no-scope-creep decision from brainstorming).
- Full design reference: `docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md`.

---

### Task 1: `ci/benchmarks/lib/live_push.sh` — periodic export + push loop

**Files:**
- Create: `ci/benchmarks/lib/live_push.sh`

**Interfaces:**
- Produces (consumed by Task 4): a script invoked two ways:
  - `live_push.sh <run_dir> <run_id> <slug>` — loops forever (caller backgrounds it). `<run_dir>` is a `.capevolve/run_suite` dir; `<run_id>` is `github.run_id`; `<slug>` is `"<tier>-<bench>"` (e.g. `smoke-tau2`).
  - `live_push.sh --cleanup <run_id> <slug>` — one-shot: deletes `live/<run_id>__<slug>` from `benchmark-history` and pushes.
  - Required env: `GH_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_WORKSPACE`, `CAPEVOLVE_PY` (all set on Actions runners except `CAPEVOLVE_PY`, exported by `ci/benchmarks/lib/ci_setup.sh`). Optional: `RUNNER_TEMP` (falls back to `/tmp`), `LIVE_REMOTE` (overrides the git remote URL — used only by the manual test in Step 3 below).

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Periodically export a still-running CapEvolve run's static dashboard data onto the
# benchmark-history branch's live/<run_id>__<tier>-<bench>/data/ dir, overwritten in
# place every cycle -- no history of intermediate snapshots is kept, only the latest --
# so site/benchmarks.html's "Running now" panel can link to a near-live SPA view.
# See docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md.
#
# Usage:
#   live_push.sh <run_dir> <run_id> <slug>     loop forever (caller backgrounds this)
#   live_push.sh --cleanup <run_id> <slug>     one-shot: delete live/<run_id>__<slug>, push
#
# <run_dir> is the .capevolve/run_suite dir that gains an events.jsonl once the suite
# starts producing events. <slug> is "<tier>-<bench>" (e.g. "smoke-tau2") -- the same
# format the `aggregate` job uses for runs/<slug>/, so both trees are keyed consistently.
#
# Env:
#   GH_TOKEN          - push access to this repo (required unless LIVE_REMOTE is set)
#   GITHUB_REPOSITORY - "owner/repo" (set by default on Actions runners)
#   GITHUB_WORKSPACE  - repo checkout root (set by default on Actions runners)
#   CAPEVOLVE_PY      - python executable with capevolve_dashboard importable (exported
#                       by ci_setup.sh)
#   RUNNER_TEMP       - scratch dir (set by default on Actions runners; falls back to /tmp)
#   LIVE_REMOTE       - override the git remote URL (used by the manual test in this
#                       task's Step 3; defaults to the token-authenticated github.com URL)
set -uo pipefail   # no -e: a failed cycle should log and retry, not kill the loop

INTERVAL=300  # 5 minutes, hardcoded -- see design doc; not worth a workflow input (YAGNI)

remote_url() {
  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
}

# Clone benchmark-history, replace live/<slug_dir> in one commit, push. Retries on
# clone/push failure (races with other concurrent bench-job pollers are expected).
#   $1 = dir whose contents become live/<slug_dir>/data/, or "" to only delete
#   $2 = slug_dir, e.g. "12345__smoke-tau2"
push_live() {
  local src="$1" slug_dir="$2" clone_dir="${RUNNER_TEMP:-/tmp}/_live_hist_$$"
  for attempt in 1 2 3; do
    rm -rf "$clone_dir"
    if ! git clone --depth 1 --branch benchmark-history "$(remote_url)" "$clone_dir" 2>/dev/null; then
      echo "live_push: clone failed (attempt $attempt)"
      sleep 3
      continue
    fi
    (
      cd "$clone_dir" || exit 1
      mkdir -p live   # ensures the pathspec below always matches, even on a first-ever push
      rm -rf "live/$slug_dir"
      if [ -n "$src" ]; then
        mkdir -p "live/$slug_dir/data"
        cp -R "$src/." "live/$slug_dir/data/"
      fi
      git add -A live
      git config user.name "skillberry-bot"
      git config user.email "actions@github.com"
      git commit -m "live: update $slug_dir" -q || exit 0
      git push origin benchmark-history
    )
    local rc=$?
    rm -rf "$clone_dir"
    [ "$rc" -eq 0 ] && return 0
    echo "live_push: push attempt $attempt failed, retrying"
    sleep 3
  done
  echo "live_push: giving up after 3 attempts (best-effort, will retry next cycle)"
  return 1
}

main() {
  if [ "${1:-}" = "--cleanup" ]; then
    local run_id="$2" slug="$3"
    push_live "" "${run_id}__${slug}" || true
    return 0
  fi

  local run_dir="$1" run_id="$2" slug="$3" slug_dir="${2}__${3}"
  while true; do
    sleep "$INTERVAL"
    if [ ! -f "$run_dir/events.jsonl" ]; then
      echo "live_push: no events.jsonl yet at $run_dir, skipping this cycle"
      continue
    fi
    local out="${RUNNER_TEMP:-/tmp}/live_export_${slug_dir}"
    rm -rf "$out"
    if PYTHONPATH="$GITHUB_WORKSPACE/dashboard/backend" "$CAPEVOLVE_PY" -m capevolve_dashboard.export_static \
        --base "$(dirname "$run_dir")" --run-id run_suite --out "$out"; then
      push_live "$out" "$slug_dir" || true
    else
      echo "live_push: export_static failed this cycle (best-effort, will retry)"
    fi
    rm -rf "$out"
  done
}

# Guard the auto-run so this file can also be `source`d (functions only) for testing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
```

- [ ] **Step 2: Syntax-check the script**

Run: `bash -n ci/benchmarks/lib/live_push.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Manually verify `push_live` against a scratch local git remote**

This exercises the actual git mechanics (clone/commit/push/retry, the `--cleanup` path,
and the "nothing changed" no-op) without needing a real GitHub Actions run. Run this in
a scratch shell (not part of the committed repo):

```bash
set -e
scratch=$(mktemp -d)

# Seed a bare "benchmark-history" remote, mirroring the real branch's shape.
git init --bare -q "$scratch/remote.git"
work=$(mktemp -d)
git init -q "$work"
git -C "$work" checkout -q -b benchmark-history
git -C "$work" commit -q --allow-empty -m init
git -C "$work" remote add origin "$scratch/remote.git"
git -C "$work" push -q origin benchmark-history

export LIVE_REMOTE="$scratch/remote.git"
export RUNNER_TEMP="$scratch"
source ci/benchmarks/lib/live_push.sh   # defines functions only; BASH_SOURCE guard prevents auto-run

# 1. Push a snapshot.
data=$(mktemp -d)
echo '{"hello":"world"}' > "$data/runs.json"
push_live "$data" "999__smoke-tau2"
git -C "$scratch/remote.git" show benchmark-history:live/999__smoke-tau2/data/runs.json
# Expected: prints {"hello":"world"}

# 2. Overwrite in place (no history kept).
echo '{"hello":"again"}' > "$data/runs.json"
push_live "$data" "999__smoke-tau2"
git -C "$scratch/remote.git" log --oneline benchmark-history | wc -l
# Expected: 3 (init + first push + this push) -- confirms overwrite, not append

# 3. Cleanup deletes the entry.
push_live "" "999__smoke-tau2"
git -C "$scratch/remote.git" show benchmark-history:live/999__smoke-tau2/data/runs.json 2>&1 || true
# Expected: "fatal: path ... does not exist" -- confirms deletion

# 4. Cleanup again (idempotent no-op -- this is what the CI "Stop" step hits for a
#    smoke run that finished before its first snapshot ever landed).
push_live "" "999__smoke-tau2"
# Expected: exits 0, no error (the `mkdir -p live` + `git commit ... || exit 0` guard)

rm -rf "$scratch" "$work" "$data"
```

Expected: all four checks match their stated expectations. This confirms the
first-ever-push, overwrite-in-place, delete, and no-op-cleanup behaviors all work
before this script is ever wired into a real CI job.

- [ ] **Step 4: Commit**

```bash
git add ci/benchmarks/lib/live_push.sh
git commit -m "feat(bench): add live_push.sh — periodic live-snapshot export/push loop"
```

---

### Task 2: Wire the poller into `.github/workflows/benchmarks.yml`

**Files:**
- Modify: `.github/workflows/benchmarks.yml` (the `bench` job — permissions, and two new steps around "Run suite")

**Interfaces:**
- Consumes: `live_push.sh <run_dir> <run_id> <slug>` and `live_push.sh --cleanup <run_id> <slug>` from Task 1.

- [ ] **Step 1: Bump the `bench` job's permissions**

In the `bench` job, change:

```yaml
    permissions:
      contents: read
      pull-requests: write
      issues: write
```

to:

```yaml
    permissions:
      contents: write
      pull-requests: write
      issues: write
```

- [ ] **Step 2: Add "Start live snapshot poller" before "Run suite"**

Insert immediately before the existing `- name: Run suite` step:

```yaml
      - name: Start live snapshot poller
        if: steps.gate.outputs.run == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          run_dir="$GITHUB_WORKSPACE/ci/benchmarks/.work/suite_${{ matrix.tier }}_${{ matrix.bench }}_proj/.capevolve/run_suite"
          nohup bash ci/benchmarks/lib/live_push.sh "$run_dir" "${{ github.run_id }}" "${{ matrix.tier }}-${{ matrix.bench }}" \
            > "$RUNNER_TEMP/live_push_${{ matrix.tier }}_${{ matrix.bench }}.log" 2>&1 &
          echo $! > "$RUNNER_TEMP/live_push_${{ matrix.tier }}_${{ matrix.bench }}.pid"
          disown
```

- [ ] **Step 3: Add "Stop live snapshot poller" after "Run suite"**

Insert immediately after the existing `- name: Run suite` step (before "Export CapEvolve UI snapshot"):

```yaml
      - name: Stop live snapshot poller
        if: steps.gate.outputs.run == 'true' && always()
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          pidfile="$RUNNER_TEMP/live_push_${{ matrix.tier }}_${{ matrix.bench }}.pid"
          if [ -f "$pidfile" ]; then
            kill "$(cat "$pidfile")" 2>/dev/null || true
            rm -f "$pidfile"
          fi
          bash ci/benchmarks/lib/live_push.sh --cleanup "${{ github.run_id }}" "${{ matrix.tier }}-${{ matrix.bench }}" \
            || echo "::warning::live cleanup push failed (best-effort, no action needed)"
```

The resulting step order in the `bench` job is: checkout → Gate → Setup runner env →
**Start live snapshot poller** → Run suite → **Stop live snapshot poller** → Export
CapEvolve UI snapshot → Write run metadata → Upload artifacts → Comment results on the PR.

- [ ] **Step 4: Validate the YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/benchmarks.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/benchmarks.yml
git commit -m "feat(bench): background a live-snapshot poller around Run suite"
```

---

### Task 3: Build the generic dashboard shell in `.github/workflows/pages.yml`

**Files:**
- Modify: `.github/workflows/pages.yml` (the `build` job)
- Modify: `.gitignore`

**Interfaces:**
- Produces: `site/dashboard-ui/index.html` (+ assets) in the Pages deploy artifact — a
  generic, run-agnostic build of the existing `dashboard/frontend` SPA, consumed at
  request time via the `?dataBase=` query param wired up in Task 4.

- [ ] **Step 1: Add the build step**

In the `build` job, insert after "Verify site/ exists" and before "Fold in
benchmark-history UI snapshots":

```yaml
      - name: Set up Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Build CapEvolve dashboard shell (generic — data source is set at request time)
        working-directory: dashboard/frontend
        run: |
          npm ci
          VITE_STATIC=1 npx vite build --outDir "$GITHUB_WORKSPACE/site/dashboard-ui"
```

This output is a normal build artifact — it lands inside `site/`, so the existing
"Upload artifact" step (`path: site/`) picks it up automatically. It is never committed
to git; a fresh build runs on every Pages deploy.

- [ ] **Step 2: Ignore the build output locally**

Add to `.gitignore`, after the "CI benchmark scratch" block:

```
# generic dashboard-ui shell built fresh by pages.yml (CI-only, never committed)
site/dashboard-ui/
```

- [ ] **Step 3: Verify the build actually produces the shell**

Run:
```bash
cd dashboard/frontend
npm ci
VITE_STATIC=1 npx vite build --outDir /tmp/dashboard-ui-check
ls /tmp/dashboard-ui-check/index.html
rm -rf /tmp/dashboard-ui-check
cd ../..
```
Expected: `ls` prints the path (file exists), confirming the exact command used in the
workflow step produces a working build.

- [ ] **Step 4: Validate the YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pages.yml .gitignore
git commit -m "feat(pages): build a generic CapEvolve dashboard shell for live/linked viewing"
```

---

### Task 4: Runtime `dataBase` override (`api.ts` + `main.tsx`)

**Files:**
- Modify: `dashboard/frontend/src/lib/api.ts`
- Modify: `dashboard/frontend/src/main.tsx`
- Create: `dashboard/frontend/src/test/data-base.test.ts`

**Interfaces:**
- Produces: `applyDataBaseOverride(search?: string): void` exported from `api.ts`,
  called once by `main.tsx` before mounting. `getJSON()`'s static-mode base path is read
  lazily via a `dataBase()` helper (not a module-level constant) so it reflects whatever
  `applyDataBaseOverride` set on `window.__CAPEVOLVE_DATA_BASE__`.

- [ ] **Step 1: Write the failing test**

Create `dashboard/frontend/src/test/data-base.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, applyDataBaseOverride } from '../lib/api'

type WindowOverride = { __CAPEVOLVE_DATA_BASE__?: string; __CAPEVOLVE_STATIC__?: unknown }

afterEach(() => {
  const w = window as unknown as WindowOverride
  delete w.__CAPEVOLVE_DATA_BASE__
  delete w.__CAPEVOLVE_STATIC__
  vi.unstubAllGlobals()
})

describe('applyDataBaseOverride', () => {
  it('sets window.__CAPEVOLVE_DATA_BASE__ from a dataBase query param', () => {
    applyDataBaseOverride('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    expect((window as unknown as WindowOverride).__CAPEVOLVE_DATA_BASE__).toBe(
      'https://example.test/live/data',
    )
  })

  it('leaves the override unset when there is no dataBase param', () => {
    applyDataBaseOverride('?foo=bar')
    expect((window as unknown as WindowOverride).__CAPEVOLVE_DATA_BASE__).toBeUndefined()
  })
})

describe('getJSON static-mode base', () => {
  it('fetches from the overridden data base when set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    applyDataBaseOverride('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return { ok: true, json: async () => [] } as Response
      }),
    )
    await api.runs()
    expect(calls[0]).toBe('https://example.test/live/data/runs.json')
  })

  it('falls back to the relative "data" base when no override is set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return { ok: true, json: async () => [] } as Response
      }),
    )
    await api.runs()
    expect(calls[0]).toBe('data/runs.json')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd dashboard/frontend && npx vitest run src/test/data-base.test.ts`
Expected: FAIL — `applyDataBaseOverride` is not exported from `../lib/api` yet.

- [ ] **Step 3: Implement `applyDataBaseOverride` and the lazy `dataBase()` in `api.ts`**

In `dashboard/frontend/src/lib/api.ts`, replace:

```ts
/** Base for the static data dir. Relative so it works from any subpath/host. */
const DATA_BASE = 'data'

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const target = STATIC_MODE ? `${DATA_BASE}/${staticSlug(url)}.json` : url
  const res = await fetch(target, { signal })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${target}`)
  }
  return (await res.json()) as T
}
```

with:

```ts
/** Base for the static data dir. Read lazily (not a module-level const) — main.tsx sets
 * window.__CAPEVOLVE_DATA_BASE__ *after* this module has already been evaluated, so a
 * top-level const would capture the default before the override lands. Relative default
 * so it still works from any subpath/host when there is no override. */
function dataBase(): string {
  const override = (window as unknown as { __CAPEVOLVE_DATA_BASE__?: string })
    .__CAPEVOLVE_DATA_BASE__
  return override || 'data'
}

/** Reads a `?dataBase=` query param and, if present, sets window.__CAPEVOLVE_DATA_BASE__
 * so getJSON() serves static requests from that (absolute) URL instead of the relative
 * default. Called once by main.tsx before mounting. */
export function applyDataBaseOverride(search: string = window.location.search): void {
  const override = new URLSearchParams(search).get('dataBase')
  if (override) {
    (window as unknown as { __CAPEVOLVE_DATA_BASE__?: string }).__CAPEVOLVE_DATA_BASE__ = override
  }
}

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const target = STATIC_MODE ? `${dataBase()}/${staticSlug(url)}.json` : url
  const res = await fetch(target, { signal })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${target}`)
  }
  return (await res.json()) as T
}
```

- [ ] **Step 4: Call it from `main.tsx`**

In `dashboard/frontend/src/main.tsx`, change:

```tsx
import { STATIC_MODE } from './lib/api'
```

to:

```tsx
import { STATIC_MODE, applyDataBaseOverride } from './lib/api'
```

and add, immediately before `createRoot(document.getElementById('root')!).render(`:

```tsx
applyDataBaseOverride()

```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd dashboard/frontend && npx vitest run src/test/data-base.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full frontend test suite and typecheck**

Run: `cd dashboard/frontend && npm test && npx tsc -b`
Expected: all tests pass; `tsc -b` exits 0 with no type errors.

- [ ] **Step 7: Commit**

```bash
git add dashboard/frontend/src/lib/api.ts dashboard/frontend/src/main.tsx dashboard/frontend/src/test/data-base.test.ts
git commit -m "feat(dashboard): support a runtime ?dataBase= override for the static SPA"
```

---

### Task 5: "Running now" panel + "Watch live" links (`site/benchmarks.html`, `site/benchmarks.js`, `site/style.css`)

**Files:**
- Modify: `site/benchmarks.html`
- Modify: `site/benchmarks.js`
- Modify: `site/style.css`

**Interfaces:**
- Consumes: `RAW` constant (already in `benchmarks.js`) as the base for building
  `live/<run_id>__<tier>-<bench>/data` URLs; `site/dashboard-ui/index.html` from Task 3
  as the link target.

- [ ] **Step 1: Add the panel markup to `benchmarks.html`**

Insert immediately before `<div class="filters">`:

```html
  <div id="running-now" class="callout callout-accent" hidden>
    <p class="callout-title">Running now</p>
    <ul id="running-list" class="running-list"></ul>
  </div>
```

- [ ] **Step 2: Bump the cache-busting version query strings**

`benchmarks.html` currently loads `style.css?v=20260724b` and
`benchmarks.js?v=20260729a`. Since both files change in this task, bump both:

```html
  <link rel="stylesheet" href="style.css?v=20260729b">
```

```html
<script src="benchmarks.js?v=20260729b" defer></script>
```

(Match whatever the existing `<script>` tag's attributes are — only the `?v=` value
changes.)

- [ ] **Step 3: Add the panel styling to `style.css`**

Add near the existing `.filters` rules:

```css
.running-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.running-list li { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
```

- [ ] **Step 4: Add the polling logic to `benchmarks.js`**

Add near the top, after the `RAW`/`RECORDS` declarations:

```js
const GH_API = "https://api.github.com/repos/skillberry-ai/cap-evolve";
const JOB_RE = /^(smoke|full) \/ (tau2|swebench|skillsbench)$/;
```

Add near the bottom, replacing the final `load();` line with:

```js
load();
loadRunning();
setInterval(loadRunning, 60000);
```

Add the two new functions (anywhere after `esc()` is defined):

```js
async function loadRunning() {
  const panel = $("#running-now");
  try {
    const runsResp = await fetch(`${GH_API}/actions/workflows/benchmarks.yml/runs?status=in_progress&per_page=20`);
    if (!runsResp.ok) throw new Error(String(runsResp.status));
    const { workflow_runs: runs } = await runsResp.json();
    const items = [];
    for (const run of runs || []) {
      const jobsResp = await fetch(`${GH_API}/actions/runs/${run.id}/jobs`);
      if (!jobsResp.ok) continue;
      const { jobs } = await jobsResp.json();
      for (const job of jobs || []) {
        if (job.status !== "in_progress") continue;
        const m = JOB_RE.exec(job.name);
        if (!m) continue;
        items.push({ runId: run.id, tier: m[1], bench: m[2], jobUrl: job.html_url });
      }
    }
    renderRunning(items);
  } catch (e) {
    panel.hidden = true;
  }
}

function renderRunning(items) {
  const panel = $("#running-now");
  const list = $("#running-list");
  if (!items.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  list.innerHTML = items.map((it) => {
    const dataBase = encodeURIComponent(`${RAW}/live/${it.runId}__${it.tier}-${it.bench}/data`);
    return `<li><span class="badge badge-accent">live</span>
      <a href="${esc(it.jobUrl)}" target="_blank" rel="noopener">${esc(it.tier)} / ${esc(it.bench)}</a>
      — <a href="./dashboard-ui/index.html?dataBase=${dataBase}#/runs/run_suite" target="_blank" rel="noopener">Watch live</a></li>`;
  }).join("");
}
```

- [ ] **Step 5: Syntax-check the script**

Run: `node --check site/benchmarks.js`
Expected: no output, exit 0.

- [ ] **Step 6: Manually verify in a browser**

```bash
cd site && python3 -m http.server 8123
```

Open `http://localhost:8123/benchmarks.html`. Expected: page loads with no console
errors; the "Running now" panel is present in the DOM (`#running-now`, currently
`hidden` since there's almost certainly no real in-progress run at test time — that's
correct, not a bug). In the browser devtools console, confirm the wiring end-to-end by
forcing a fake result through the render path:

```js
renderRunning([{ runId: 999, tier: "smoke", bench: "tau2", jobUrl: "https://example.com" }])
```

Expected: the panel becomes visible with one "smoke / tau2" row, a "live" badge, and a
working "Watch live" link whose href is
`./dashboard-ui/index.html?dataBase=<encoded .../live/999__smoke-tau2/data>#/runs/run_suite`.
Stop the server (`Ctrl-C`) when done.

- [ ] **Step 7: Commit**

```bash
git add site/benchmarks.html site/benchmarks.js site/style.css
git commit -m "feat(site): show in-progress benchmark runs with a Watch live link"
```

---

### Task 6: Document the feature in `ci/benchmarks/README.md`

**Files:**
- Modify: `ci/benchmarks/README.md`

- [ ] **Step 1: Add a new subsection after "Per-run CapEvolve UI snapshots"**

Insert immediately after the existing "Per-run CapEvolve UI snapshots" section (the one
ending with "...that's an accepted tradeoff for keeping 'keep forever unless a human
explicitly prunes' simple."):

```markdown
### Live monitoring while a run is in progress

Each `bench` job also backgrounds `ci/benchmarks/lib/live_push.sh` around "Run suite":
every 5 minutes it exports the in-progress run's static dashboard data and overwrites
`live/<run_id>__<tier>-<bench>/data/` on `benchmark-history` — always the latest
snapshot only, never a history of intermediate ones. When the job ends (any outcome),
it deletes that `live/` entry; the permanent snapshot lands moments later via the
`aggregate` job's `runs/<slug>/` write, same as always.

`benchmarks.html` polls the GitHub Actions API client-side (unauthenticated, no new
CI-side status reporting) to show a "Running now" panel with a "Watch live" link per
in-progress `<tier>/<bench>` job. Unlike the finished-run UI (a full shell+data copy
committed per run), the live view points one generic dashboard shell — built once per
Pages deploy at `site/dashboard-ui/` — at the live data via a `?dataBase=` query param,
so no Pages redeploy is needed while a run is in progress.

Orphaned `live/` entries (e.g. a hard runner crash before cleanup runs) are harmless:
"what's running" is always derived from the GitHub Actions API, never from `live/`'s
existence, so an orphan is simply never linked to.
```

- [ ] **Step 2: Commit**

```bash
git add ci/benchmarks/README.md
git commit -m "docs(bench): document live run monitoring"
```

---

## Self-Review Notes

- **Spec coverage:** Architecture §1 (detection) → Task 5. §2 (periodic push) → Tasks 1
  and 2. §3 (viewing) → Tasks 3 and 4. Edge cases (no snapshot yet, orphaned entries,
  push races, rate limits) → covered by `live_push.sh`'s retry loop (Task 1) and the
  README note (Task 6); no dedicated task needed since they're absorbed by existing
  design choices rather than new code. Testing section → Task 1 Step 3 (push mechanics),
  Task 4 (vitest), Tasks 2/3 (`yaml.safe_load`).
- **Type/interface consistency:** `applyDataBaseOverride`, `dataBase()`, `push_live()`,
  and the CLI arg order for `live_push.sh` are named identically everywhere they're
  defined and consumed across Tasks 1–4.
- **No placeholders:** every step above contains complete, runnable code — no TBDs.
