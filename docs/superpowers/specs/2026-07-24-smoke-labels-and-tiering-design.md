# Smoke labels + test tiering — Design

**Date:** 2026-07-24
**Status:** Approved design, pre-implementation
**Branch:** `feat/smoke-labels-and-tiering`

## Problem

Two gaps in the `ci/benchmarks` workflow:
1. On a PR, the single `benchmark-test` label runs **all three** benchmarks — no way to run just one.
2. The suite is a **smoke** regression (2 hard tasks per benchmark), but nothing in the labels,
   checks, report, or history page says so — it reads like the full benchmark.

Additionally, **full** (non-smoke) tests will later be added to the **same** `Benchmarks`
workflow and the **same** history page. So "smoke" must be a *tier*, not the identity of the
workflow/page.

## Goals

- Per-benchmark PR selection via labels.
- Mark smoke runs as smoke **everywhere they surface**, while keeping the workflow named
  `Benchmarks` and the history page shared across tiers.
- Leave clean seams so a future `full` tier drops in with minimal change.

## Decisions (confirmed)

- **Labels:** rename `benchmark-test` → **`benchmark-smoke`** (all); add
  **`benchmark-smoke-tau2` / `-swebench` / `-skillsbench`** (per-bench, combinable).
  Future full tier mirrors as `benchmark-full*`.
- **Tier is a first-class dimension:** `smoke` now, `full` later — not a global rename.
- Workflow name stays **`Benchmarks`**; history page title/nav stay **`Benchmarks`**.

## Design

### Labels (repo state, via `gh`)
- `gh label edit benchmark-test --name benchmark-smoke` (in-place → migrates PR #55's label).
- `gh label create benchmark-smoke-{tau2,swebench,skillsbench}`.

### `.github/workflows/benchmarks.yml`
- `name: Benchmarks` unchanged.
- Matrix gains a tier dimension (only smoke today):
  ```yaml
  matrix:
    tier: [smoke]
    bench: [tau2, swebench, skillsbench]
  ```
- Job name → `${{ matrix.tier }} / ${{ matrix.bench }}` → PR checks read **`smoke / tau2`**.
- `concurrency.group` includes tier.
- Job-level `if` (PR path): run when any label contains the tier prefix —
  `contains(join(github.event.pull_request.labels.*.name, ','), 'benchmark-smoke')`
  (matches both `benchmark-smoke` and `benchmark-smoke-<bench>`).
- Per-matrix `Gate` step sets `run`:
  - `workflow_dispatch`: existing `inputs.benchmark` (all / one), unchanged.
  - `pull_request`: run if labels contain `benchmark-smoke` **or**
    `format('benchmark-smoke-{0}', matrix.bench)`.
- `Write run metadata` step adds `"tier": "${{ matrix.tier }}"` to `runmeta.json`.
- `TIER: ${{ matrix.tier }}` in job env, passed to `run_suite.sh`.

### `ci/benchmarks/lib/run_suite.sh`
- Report header tier-driven: `## ${TIER^} suite — $BENCH` → `## Smoke suite — tau2`
  (falls back to `smoke` if `TIER` unset).

### `ci/benchmarks/lib/record.py`
- No code change: `build_record` already merges `runmeta` verbatim, so `tier` flows into the
  record. Add a unit test asserting `tier` passthrough + a default when absent.

### `site/benchmarks.html` + `benchmarks.js`
- Title / nav / H1 stay **"Benchmarks"** (shared across tiers).
- Add a **"Type"** column (renders `r.tier || 'smoke'`) and a **tier filter**
  (all / smoke / full).
- Update the empty-state hint: `benchmark-test` → `benchmark-smoke`.
- Lead copy notes runs are smoke or full.

### `ci/benchmarks/README.md`
- Trigger section: `benchmark-smoke` (all) + per-bench labels; note the smoke tier and that
  full is a future tier in the same workflow.

## Not building now (YAGNI — full's shape is unspecified)
- The `full` task sets / `tasks.json` wiring and `benchmark-full*` labels. Only the seams
  (tier matrix, tier field, tier-driven names, Type column/filter) are added so full is a
  small later change.

## Backward compatibility
- Records already pushed (pre-tier) have no `tier`; the page defaults missing → `smoke`
  (correct, since all historical runs are smoke).
- Sticky-comment marker `<!-- benchmarks:<bench> -->` unchanged (no orphaned comments).
- Renaming the matrix/check name to `smoke / <bench>` changes PR check names; if any branch
  protection requires the old names, update it (admin available).

## Testing
- `record.py` unit test: `tier` passthrough + default.
- YAML lint; extract + run the gate logic mentally / dry-run against label combos.
- Page: fixture with a smoke + a (hypothetical) full record → Type column + tier filter render;
  missing-tier record shows "smoke".
