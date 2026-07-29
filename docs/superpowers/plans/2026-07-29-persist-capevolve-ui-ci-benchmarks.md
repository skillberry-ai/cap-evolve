# Persist CapEvolve UI for CI Benchmark Runs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a browsable static CapEvolve dashboard snapshot for every CI benchmark run (success/failure/cancelled) onto the existing `benchmark-history` branch, and link to it from `site/benchmarks.html`, with no automatic expiry and a manually-triggered prune workflow.

**Architecture:** The self-hosted `bench` job (per matrix cell) best-effort-exports the run's raw `.capevolve` directory to static JSON via the existing `export_static.py`, riding along in the artifact it already uploads. The `aggregate` job (ubuntu-latest) builds the Vite static shell once, assembles each artifact's `ui/data/` into `runs/<run_id>__<tier>-<bench>/ui/` on `benchmark-history`, and stamps `has_ui: true` on the matching record. `pages.yml` gains a `workflow_run` trigger that folds `benchmark-history`'s `runs/**` into the Pages deploy under `benchmark-ui/runs/**`. `benchmarks.js` renders an "Open UI" link for any record with `has_ui: true`. A new `benchmark-history-prune.yml` workflow (`workflow_dispatch` only) lets a maintainer delete records + paired UI snapshots older than N days (default 30) — this is the *only* deletion path; nothing is automatic.

**Tech Stack:** GitHub Actions (`workflow_dispatch`, `pull_request`, `workflow_run`), Python 3 (`ci/benchmarks/lib/record.py`, `pytest`), Node 22 / Vite (`dashboard/frontend`, `VITE_STATIC=1`), vanilla JS (`site/benchmarks.js`), git orphan branch (`benchmark-history`).

## Global Constraints

- No automatic retention/expiry of any kind — records and UI snapshots on `benchmark-history` are kept forever by default.
- Deletion only happens via the new manual `workflow_dispatch` prune workflow, with a `days` input defaulting to `"30"`.
- Everything lives on the single existing `benchmark-history` branch — no new branch.
- No changes to the live `dashboard/` app itself — reuse `export_static.py` and the `VITE_STATIC=1` Vite build exactly as they exist today.
- The `bench` job's export step must be best-effort (`if: always()`, never fails the job) since it must still attempt to run on a cancelled job.
- Don't modify `ci/benchmarks/lib/ci_setup.sh` — run `export_static.py` via `PYTHONPATH="$GITHUB_WORKSPACE/dashboard/backend"` against the already-cached `$CAPEVOLVE_PY` venv instead of installing `dashboard/backend`'s FastAPI/uvicorn deps.
- Design doc of record: `docs/superpowers/specs/2026-07-29-persist-capevolve-ui-ci-benchmarks-design.md`. Follow it exactly; this plan is its task breakdown.

---

### Task 1: `record.py` — add `has_ui` field + CLI flag

**Files:**
- Modify: `ci/benchmarks/lib/record.py:53-71` (`build_record`), `ci/benchmarks/lib/record.py:81-98` (`main`/CLI)
- Test: `ci/benchmarks/lib/test_record.py`

**Interfaces:**
- Produces: `build_record(metrics_jsonl: Path, runmeta: dict, steps_jsonl: Path | None = None, has_ui: bool = False) -> dict` — return dict gains `rec["has_ui"]` (bool). CLI `build` subcommand gains `--has-ui` (`store_true`).

- [ ] **Step 1: Write the failing tests**

Append to `ci/benchmarks/lib/test_record.py` (after `test_build_preserves_tier`):

```python
def test_build_has_ui_true(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK])
    meta = {"run_id": 10, "bench": "tau2", "conclusion": "success", "date": "d"}
    rec = record.build_record(m, meta, has_ui=True)
    assert rec["has_ui"] is True


def test_build_has_ui_defaults_false(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK])
    meta = {"run_id": 11, "bench": "tau2", "conclusion": "success", "date": "d"}
    rec = record.build_record(m, meta)
    assert rec["has_ui"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ci/benchmarks/lib && python3 -m pytest test_record.py -k has_ui -v`
Expected: FAIL — `KeyError: 'has_ui'` (the field doesn't exist yet) or `TypeError: build_record() got an unexpected keyword argument 'has_ui'`.

- [ ] **Step 3: Implement `has_ui` in `build_record`**

In `ci/benchmarks/lib/record.py`, change the `build_record` signature and body (line 53-71):

```python
def build_record(
    metrics_jsonl: Path,
    runmeta: dict,
    steps_jsonl: Path | None = None,
    has_ui: bool = False,
) -> dict:
    tasks: list[dict] = []
    if metrics_jsonl.exists():
        for line in metrics_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    steps: list[dict] = []
    if steps_jsonl and steps_jsonl.exists():
        for line in steps_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                steps.append(json.loads(line))
    rec = dict(runmeta)
    rec["schema"] = SCHEMA
    rec["tasks"] = tasks
    rec["steps"] = steps
    rec["suite"] = rollup(tasks, steps) if runmeta.get("conclusion") == "success" else None
    rec["has_ui"] = has_ui
    return rec
```

- [ ] **Step 4: Add the `--has-ui` CLI flag**

In `ci/benchmarks/lib/record.py`, in `main()` (line 81-98), add the flag to the `build` subparser and pass it through:

```python
    b = sub.add_parser("build")
    b.add_argument("metrics")
    b.add_argument("--runmeta", required=True)
    b.add_argument("--steps", default=None)
    b.add_argument("--has-ui", action="store_true")
```

and change the `build` branch's call:

```python
    if ns.cmd == "build":
        runmeta = json.loads(Path(ns.runmeta).read_text(encoding="utf-8"))
        steps_path = Path(ns.steps) if ns.steps else None
        print(json.dumps(build_record(Path(ns.metrics), runmeta, steps_path, has_ui=ns.has_ui)))
        return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ci/benchmarks/lib && python3 -m pytest test_record.py -v`
Expected: all tests PASS, including the 2 new ones and all pre-existing ones (`test_build_success` etc. — confirm the new optional `has_ui` param with a default doesn't break any 3-positional-arg call site).

- [ ] **Step 6: Commit**

```bash
git add ci/benchmarks/lib/record.py ci/benchmarks/lib/test_record.py
git commit -m "feat(bench): add has_ui field to benchmark-history records"
```

---

### Task 2: `benchmarks.yml` — export the CapEvolve UI snapshot in the `bench` job

**Files:**
- Modify: `.github/workflows/benchmarks.yml:213-216` (insert a new step between "Run suite" and "Write run metadata")

**Interfaces:**
- Consumes: `export_static.py`'s existing CLI (`--base`, `--run-id`, `--out`) — unmodified. `$CAPEVOLVE_PY` env var, already exported to `$GITHUB_ENV` by `ci_setup.sh`.
- Produces: `ci/benchmarks/.work/suite_<tier>_<bench>/ui/data/*.json` inside the job's existing `out` dir — rides along in the artifact `actions/upload-artifact@v4` already uploads (path `ci/benchmarks/.work/suite_${{ matrix.tier }}_${{ matrix.bench }}/**`, unchanged). Task 3 (`aggregate` job) looks for a `ui/data/` subdirectory inside each downloaded artifact.

- [ ] **Step 1: Insert the export step**

In `.github/workflows/benchmarks.yml`, insert this new step immediately after the "Run suite" step (line 215) and before "Write run metadata" (line 217):

```yaml
      - name: Export CapEvolve UI snapshot
        if: steps.gate.outputs.run == 'true' && always()
        run: |
          run_dir="$GITHUB_WORKSPACE/ci/benchmarks/.work/suite_${{ matrix.tier }}_${{ matrix.bench }}_proj/.capevolve/run_suite"
          out="$GITHUB_WORKSPACE/ci/benchmarks/.work/suite_${{ matrix.tier }}_${{ matrix.bench }}"
          if [ -f "$run_dir/events.jsonl" ]; then
            PYTHONPATH="$GITHUB_WORKSPACE/dashboard/backend" "$CAPEVOLVE_PY" -m capevolve_dashboard.export_static \
              --base "$(dirname "$run_dir")" --run-id run_suite --out "$out/ui/data" \
              || echo "::warning::UI export failed for ${{ matrix.tier }}/${{ matrix.bench }} (best-effort, continuing)"
          else
            echo "no run dir at $run_dir (job likely failed/cancelled before producing one) — skipping UI export"
          fi
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/benchmarks.yml')); print('ok')"`
Expected: `ok` (no `yaml.scanner.ScannerError`/`yaml.parser.ParserError`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/benchmarks.yml
git commit -m "feat(bench): export CapEvolve UI snapshot in the bench job"
```

---

### Task 3: `benchmarks.yml` — assemble UI snapshots + `has_ui` in the `aggregate` job

**Files:**
- Modify: `.github/workflows/benchmarks.yml:279-343` (whole `aggregate` job)

**Interfaces:**
- Consumes: `record.py build --has-ui` (Task 1). Each artifact's optional `ui/data/` dir (Task 2). `dashboard/frontend`'s existing `npm ci` / `VITE_STATIC=1 npx vite build` convention (mirrors `.github/workflows/ci.yml`'s `build-dashboard` job).
- Produces: `_hist/runs/<run_id>__<tier>-<bench>/ui/` pushed to `benchmark-history` alongside `records/`. `concurrency: group: benchmark-history-write` — Task 4's prune workflow uses the same group name so the two never race.

- [ ] **Step 1: Replace the `aggregate` job**

In `.github/workflows/benchmarks.yml`, replace the entire `aggregate` job (lines 279-343) with:

```yaml
  aggregate:
    name: aggregate history
    needs: [bench]
    if: always()
    runs-on: ubuntu-latest
    permissions:
      contents: write
    concurrency:
      group: benchmark-history-write
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4              # for ci/benchmarks/lib/record.py

      - name: Download all benchmark artifacts
        uses: actions/download-artifact@v4
        with:
          path: _artifacts
          pattern: benchmarks-*

      - name: Check for UI snapshots
        id: uicheck
        run: |
          if find _artifacts -type d -path '*/ui/data' 2>/dev/null | grep -q .; then
            echo "found=true" >> "$GITHUB_OUTPUT"
          else
            echo "found=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Set up Node.js 22
        if: steps.uicheck.outputs.found == 'true'
        uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Build static dashboard shell
        if: steps.uicheck.outputs.found == 'true'
        working-directory: dashboard/frontend
        run: |
          npm ci
          VITE_STATIC=1 npx vite build --outDir "$RUNNER_TEMP/ui_shell"

      - name: Build records + assemble UI snapshots
        run: |
          # upload-artifact stores files flat at the artifact root (the least-common-ancestor
          # of ci/benchmarks/.work/suite_<tier>_<bench>/** is that dir), so runmeta.json/
          # metrics.jsonl/ui/ live directly under _artifacts/benchmarks-<tier>-<bench>/. The dir
          # suffix is the <tier>-<bench> slug — use it verbatim to keep record files unique
          # per (run, tier, bench) so smoke and full of the same bench never collide.
          mkdir -p _new_records _hist_runs
          have=0; built=0
          for d in _artifacts/benchmarks-*; do
            [ -d "$d" ] || continue
            slug="$(basename "$d" | sed 's/^benchmarks-//')"   # e.g. smoke-tau2 / full-tau2
            rm="$d/runmeta.json"; metrics="$d/metrics.jsonl"; steps="$d/steps.jsonl"
            [ -f "$rm" ] || { echo "::warning::no runmeta for $slug, skipping"; continue; }
            have=$((have+1))
            rid="$(python3 -c "import json;print(json.load(open('$rm'))['run_id'])")"
            has_ui_flag=""
            if [ -d "$d/ui/data" ] && [ -n "$(ls -A "$d/ui/data" 2>/dev/null)" ]; then
              dest="_hist_runs/${rid}__${slug}/ui"
              mkdir -p "$dest"
              cp -R "$RUNNER_TEMP/ui_shell/." "$dest/"
              cp -R "$d/ui/data" "$dest/data"
              has_ui_flag="--has-ui"
            fi
            python3 ci/benchmarks/lib/record.py build "$metrics" --runmeta "$rm" --steps "$steps" $has_ui_flag \
              > "_new_records/${rid}__${slug}.json" && built=$((built+1))
            echo "built _new_records/${rid}__${slug}.json"
          done
          ls -la _new_records || true
          # Guard: if artifacts with runmeta exist but produced no records, fail loudly
          # instead of silently exiting 0 (which previously masked a path bug).
          if [ "$have" -gt 0 ] && [ "$built" -lt "$have" ]; then
            echo "::error::found $have runmeta artifact(s) but built only $built record(s)"; exit 1
          fi

      - name: Push to benchmark-history (single writer, with rebase-retry)
        run: |
          [ -n "$(ls -A _new_records 2>/dev/null)" ] || { echo "no records to push"; exit 0; }
          git config --global user.name "skillberry-bot"
          git config --global user.email "actions@github.com"
          for attempt in 1 2 3 4 5; do
            rm -rf _hist
            git clone --depth 1 --branch benchmark-history \
              "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" _hist || {
                echo "branch missing — bootstrap it per ci/benchmarks/README.md"; exit 1; }
            mkdir -p _hist/records
            cp _new_records/*.json _hist/records/
            if [ -d _hist_runs ] && [ -n "$(ls -A _hist_runs 2>/dev/null)" ]; then
              mkdir -p _hist/runs
              cp -R _hist_runs/. _hist/runs/
            fi
            python3 ci/benchmarks/lib/record.py aggregate _hist/records \
              --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --out _hist
            cd _hist
            git add records benchmarks.json meta.json
            [ -d runs ] && git add runs
            git commit -m "bench: record run ${{ github.run_id }}" || { echo "nothing to commit"; exit 0; }
            if git push origin benchmark-history; then echo "pushed"; exit 0; fi
            echo "push race, retrying ($attempt)"; cd ..; sleep 3
          done
          echo "failed to push after retries"; exit 1
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/benchmarks.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/benchmarks.yml
git commit -m "feat(bench): assemble UI snapshots and stamp has_ui in the aggregate job"
```

---

### Task 4: New manual prune workflow — `.github/workflows/benchmark-history-prune.yml`

**Files:**
- Create: `.github/workflows/benchmark-history-prune.yml`

**Interfaces:**
- Consumes: `ci/benchmarks/lib/record.py aggregate` (unchanged CLI). Same `benchmark-history-write` concurrency group as Task 3, so this and the `aggregate` job never race.

- [ ] **Step 1: Create the workflow file**

```yaml
name: Prune benchmark-history

# Manual-only deletion. benchmark-history keeps every record + UI snapshot
# forever by default (see docs/superpowers/specs/2026-07-29-persist-capevolve-ui-ci-benchmarks-design.md).
# Run this on demand to delete anything older than N days once the branch grows too large.
# Note: this deletes files in a new commit — it does not rewrite git history, so it
# does not reclaim .git object storage. It only changes what benchmark-history currently
# serves (records/, runs/, benchmarks.json, meta.json).

on:
  workflow_dispatch:
    inputs:
      days:
        description: "Delete records (and their UI snapshots) older than this many days"
        type: string
        default: "30"

permissions:
  contents: write

concurrency:
  group: benchmark-history-write
  cancel-in-progress: false

jobs:
  prune:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4              # for ci/benchmarks/lib/record.py

      - name: Prune records + UI snapshots older than cutoff
        env:
          DAYS: ${{ github.event.inputs.days || '30' }}
        run: |
          git config --global user.name "skillberry-bot"
          git config --global user.email "actions@github.com"
          for attempt in 1 2 3 4 5; do
            rm -rf _hist
            git clone --depth 1 --branch benchmark-history \
              "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" _hist || {
                echo "branch missing — bootstrap it per ci/benchmarks/README.md"; exit 1; }
            cutoff="$(date -u -d "-${DAYS} days" +%Y-%m-%dT%H:%M:%SZ)"
            echo "pruning records older than $cutoff"
            deleted=0
            for f in _hist/records/*.json; do
              [ -f "$f" ] || continue
              date_val="$(python3 -c "import json;print(json.load(open('$f')).get('date',''))")"
              if [[ -n "$date_val" && "$date_val" < "$cutoff" ]]; then
                slug="$(basename "$f" .json)"
                echo "deleting $slug (date=$date_val)"
                rm -f "$f"
                rm -rf "_hist/runs/$slug"
                deleted=$((deleted+1))
              fi
            done
            echo "deleted $deleted record(s)"
            echo "### Prune summary" >> "$GITHUB_STEP_SUMMARY"
            echo "cutoff: $cutoff (older than ${DAYS}d) — deleted $deleted record(s)" >> "$GITHUB_STEP_SUMMARY"
            python3 ci/benchmarks/lib/record.py aggregate _hist/records \
              --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --out _hist
            cd _hist
            git add records benchmarks.json meta.json
            [ -d runs ] && git add runs
            git commit -m "bench: prune records older than ${DAYS}d ($deleted deleted)" || { echo "nothing to commit"; exit 0; }
            if git push origin benchmark-history; then echo "pushed"; exit 0; fi
            echo "push race, retrying ($attempt)"; cd ..; sleep 3
          done
          echo "failed to push after retries"; exit 1
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/benchmark-history-prune.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/benchmark-history-prune.yml
git commit -m "feat(bench): add manual workflow to prune old benchmark-history records+UI"
```

---

### Task 5: `pages.yml` — fold `benchmark-history`'s `runs/` into the Pages deploy

**Files:**
- Modify: `.github/workflows/pages.yml` (whole file)

**Interfaces:**
- Consumes: `benchmark-history`'s `runs/**` (public, unauthenticated clone — same branch the `RAW` fetch in `benchmarks.js` already reads).
- Produces: deployed Pages tree gains `benchmark-ui/runs/<run_id>__<tier>-<bench>/ui/index.html` — the exact path Task 6's "Open UI" link points to.

- [ ] **Step 1: Replace the whole file**

```yaml
name: Deploy GitHub Pages

# Publish the cap-evolve site from site/ to GitHub Pages.
#
# Triggers:
#   - push to main that touches site/ or this workflow → auto-deploy
#   - manual dispatch → deploy on demand
#   - the Benchmarks workflow completing → redeploy so a new run's CapEvolve UI
#     snapshot (benchmark-history's runs/**) becomes browsable
#
# What it does: uploads site/ (plus benchmark-history's runs/** folded in under
# site/benchmark-ui/runs/**) as the Pages artifact and hands it to the official
# Pages deploy action. No build step for site/ itself (static HTML/CSS/PNG only).

on:
  push:
    branches: [main]
    paths:
      - "site/**"
      - ".github/workflows/pages.yml"
  workflow_dispatch:
  workflow_run:
    workflows: ["Benchmarks"]
    types: [completed]

permissions:
  contents: read
  pages: write
  id-token: write

# Only one Pages deployment at a time; cancel any in-progress deploy when a
# newer commit lands.
concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      # Explicit ref: main — workflow_run's default checkout otherwise resolves to
      # the SHA of the triggering Benchmarks run, which can be a PR branch. Pages
      # must always deploy main's site/, regardless of what triggered this build.
      - uses: actions/checkout@v4
        with:
          ref: main

      - name: Verify site/ exists
        run: |
          test -d site || { echo "no site/ directory"; exit 1; }
          test -f site/index.html || { echo "no site/index.html"; exit 1; }
          ls -la site/

      - name: Fold in benchmark-history UI snapshots
        run: |
          rm -rf _bench_history
          git clone --depth 1 --branch benchmark-history \
            "https://github.com/${{ github.repository }}.git" _bench_history || {
              echo "benchmark-history branch not found — deploying without UI snapshots"; exit 0; }
          mkdir -p site/benchmark-ui
          if [ -d _bench_history/runs ]; then
            cp -R _bench_history/runs site/benchmark-ui/runs
          fi

      - name: Configure Pages
        uses: actions/configure-pages@v5

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "feat(pages): redeploy on Benchmarks completion and fold in benchmark-history UI snapshots"
```

---

### Task 6: `benchmarks.html` / `benchmarks.js` / fixture — the "Open UI" link

**Files:**
- Modify: `site/benchmarks.html:102-119` (table header), `site/benchmarks.html:145` (cache-bust version)
- Modify: `site/benchmarks.js:91-122` (`render()`)
- Modify: `site/benchmarks.fixture.json:2-43` (first example record)

**Interfaces:**
- Consumes: `r.has_ui` (bool, Task 1/3), `r.run_id`, `r.tier`, `r.bench` — all already present on every record.
- Produces: an `<a>` link to `./benchmark-ui/runs/<run_id>__<tier>-<bench>/ui/index.html#/runs/run_suite`, matching the path Task 5 assembles.

- [ ] **Step 1: Add the "UI" column header**

In `site/benchmarks.html`, in the `<thead><tr>` block (lines 103-117), add a new `<th>` right after the `conclusion` column:

```html
      <th data-k="conclusion">Result</th>
      <th>UI</th>
    </tr></thead>
```

(replacing the existing `<th data-k="conclusion">Result</th>\n    </tr></thead>` at lines 116-117).

- [ ] **Step 2: Bump the script cache-bust version**

In `site/benchmarks.html` line 145, change:

```html
<script src="benchmarks.js?v=20260728a"></script>
```

to:

```html
<script src="benchmarks.js?v=20260729a"></script>
```

- [ ] **Step 3: Render the "Open UI" link in `render()`**

In `site/benchmarks.js`, in the per-row loop (lines 91-122), add a computed `ui` variable alongside the other computed cell values (after the `latency` line, before `src`):

```javascript
    const ui = r.has_ui
      ? `<a href="./benchmark-ui/runs/${encodeURIComponent(r.run_id)}__${esc(r.tier || "smoke")}-${encodeURIComponent(r.bench)}/ui/index.html#/runs/run_suite" target="_blank" rel="noopener">Open UI</a>`
      : `<span class="muted">—</span>`;
```

then append a `<td>${ui}</td>` cell to `tr.innerHTML` right after the `<td>${badge}</td>` cell (line 110):

```javascript
    tr.innerHTML = `<td><a href="${esc(r.run_url)}">${date}</a></td>
      <td>${src}</td><td>${esc(r.bench)}</td><td>${tier}</td><td>${r.iterations ?? "—"}</td>
      <td>${r.trials ?? "—"}</td>
      <td>${reward}</td><td>${evalUsd}</td><td>${optUsd}</td><td>${latency}</td>
      <td><code>${esc(r.agent_model || "—")}</code></td><td><code>${esc(r.optimizer_model || "—")}</code></td>
      <td>${badge}</td><td>${ui}</td>`;
```

and bump the detail row's `colspan` from `13` to `14` (line 116):

```javascript
    detail.innerHTML = `<td colspan="14">${taskTable(r.tasks || [])}${stepsTable(r.steps || [])}</td>`;
```

- [ ] **Step 4: Add a `has_ui` example to the fixture**

In `site/benchmarks.fixture.json`, add `"has_ui": true,` to the first record (run_id 123) right after its `"conclusion": "success",` line (line 18):

```json
    "conclusion": "success",
    "has_ui": true,
```

- [ ] **Step 5: Manually verify rendering**

Run: `cd site && python3 -m http.server 8123` then open `http://localhost:8123/benchmarks.html` in a browser. Since the page fetches the live `benchmark-history` branch (not the fixture) by default, temporarily point `RAW` in `benchmarks.js` at the fixture to check rendering — or simply eyeball the table: confirm a new "UI" column header renders, and that expanding a row (click) still shows the correct detail table without a layout break (colspan mismatch would show a jagged detail row). Revert any temporary `RAW` edit before committing.
Expected: table renders with the new "UI" column; rows with `has_ui: true` show an "Open UI" link, others show "—"; detail rows span the full width cleanly.

- [ ] **Step 6: Commit**

```bash
git add site/benchmarks.html site/benchmarks.js site/benchmarks.fixture.json
git commit -m "feat(site): render Open UI link on benchmark-history rows with has_ui"
```

---

### Task 7: Document the new pieces in `ci/benchmarks/README.md`

**Files:**
- Modify: `ci/benchmarks/README.md:146-161` ("Benchmark history page" section)

**Interfaces:** None (documentation only).

- [ ] **Step 1: Extend the "Benchmark history page" section**

In `ci/benchmarks/README.md`, replace the "Benchmark history page" section (lines 146-161) with:

```markdown
## Benchmark history page

Every run appends a per-`(run×bench)` record to the **`benchmark-history`** orphan branch
(`records/<run_id>__<tier>-<bench>.json`) and regenerates `benchmarks.json` + `meta.json` there
(single-writer `aggregate` job → no races). The Pages page `site/benchmarks.html` fetches
`benchmarks.json` at load and renders a sortable/filterable table (rollup rows expand to
per-task detail). Bootstrap the branch once:

```bash
git switch --orphan benchmark-history
mkdir -p records && : > records/.gitkeep
echo '[]' > benchmarks.json
echo '{"count":0,"runs":0,"updated":null}' > meta.json
git add records/.gitkeep benchmarks.json meta.json
git commit -m "chore: init benchmark-history branch" && git push origin benchmark-history
```

### Per-run CapEvolve UI snapshots

Each `bench` job also best-effort-exports its raw `.capevolve` run directory as a static
CapEvolve dashboard snapshot (`export_static.py` + a `VITE_STATIC=1` Vite build), assembled
by the `aggregate` job into `runs/<run_id>__<tier>-<bench>/ui/` on `benchmark-history`
alongside its record, which gets `"has_ui": true`. `pages.yml` redeploys on every Benchmarks
completion and folds `benchmark-history`'s `runs/**` into the deployed site under
`benchmark-ui/runs/**`, so `benchmarks.html` can link "Open UI" straight to a specific run's
dashboard. Records/snapshots are **kept forever by default** — there is no automatic expiry.

To reclaim space, run **Actions → "Prune benchmark-history" → Run workflow** with a `days`
input (default `30`) — it deletes any record (and its paired UI snapshot) older than that
many days, directly on `benchmark-history`. This only removes files from the branch's current
tree; it does not rewrite git history, so it doesn't reclaim `.git` object storage — that's
an accepted tradeoff for keeping "keep forever unless a human explicitly prunes" simple.
```

- [ ] **Step 2: Commit**

```bash
git add ci/benchmarks/README.md
git commit -m "docs(bench): document per-run UI snapshots and the manual prune workflow"
```

---

## Self-Review

**Spec coverage:**
- Data model (`has_ui` field, `runs/<slug>/ui/`) — Task 1, 3. ✅
- Bench-job export step, best-effort/`always()` — Task 2. ✅
- Aggregate-job shell build + assemble + push, `concurrency` group — Task 3. ✅
- Manual prune workflow (`days` input, default 30, deletes records+runs, same concurrency group) — Task 4. ✅
- `pages.yml` `workflow_run` trigger + combined artifact — Task 5. ✅
- `benchmarks.html`/`benchmarks.js` "Open UI" link — Task 6. ✅
- Testing section: `record.py` unit tests (Task 1), fixture + manual render check (Task 6). The design doc's suggestion to exercise `export_static.py` via a real smoke-tier CI run and to dry-run the prune workflow against a scratch branch are operational verifications to perform after this PR merges and runs once in CI — not unit-testable inline; noted here rather than fabricated as a task.

**Placeholder scan:** No TBD/TODO; every step has literal file content, exact paths, and runnable commands.

**Type/signature consistency:** `build_record(..., has_ui: bool = False)` (Task 1) is called identically in Task 3's `record.py build ... $has_ui_flag` (CLI, not the Python function) and in Task 1's own tests — consistent. `r.has_ui` (JS, Task 6) matches the JSON key `has_ui` set by Task 1/3. The UI path `runs/<run_id>__<tier>-<bench>/ui/` is identical across Task 3 (`_hist_runs/${rid}__${slug}/ui`, where `slug = <tier>-<bench>`) and Task 6's link construction — verified the slug order matches (`basename` strips the `benchmarks-` prefix from an artifact named `benchmarks-<tier>-<bench>`, leaving `<tier>-<bench>`).
