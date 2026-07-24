# Full benchmark tier — Design

**Date:** 2026-07-24
**Status:** Approved design, pre-implementation
**Branch:** `feat/full-benchmark-tier`

## Problem / goal

The smoke tier shipped (PR #80). Add a **`full`** tier — the whole/representative benchmark
per bench, with **frozen baselines** (like smoke) — to the same `Benchmarks` workflow and the
same history page, plus its labels.

Hard constraint: full task lists + frozen baselines require **real model runs on skillberry-1**;
they can't be generated in the PR. So this PR ships the *support* (layout, labels, gating,
tier-aware scripts, docs); the operator populates `full/tasks.json` + baselines on the runner.

## Decisions (confirmed)

- Full = whole/representative benchmark per bench; **frozen** baselines.
- Ships as plumbing; `full/tasks.json` seeded empty → full jobs no-op until populated (safe).

## Design

### Tier-aware layout (migrate smoke, add full)
- `ci/benchmarks/<bench>/tasks.json` → **`<bench>/smoke/tasks.json`**.
- `ci/benchmarks/<bench>/<task>/baseline/` → **`<bench>/smoke/<task>/baseline/`**.
- New **`<bench>/full/tasks.json`** = `[]` (seed) + `<bench>/full/<task>/baseline/` frozen later.
- `baselines.json` (metrics reference): re-nest `bench→task` under **`bench→smoke→task`**;
  `freeze_baseline.sh` writes `bench→<tier>→task`.

### Labels (via `gh`)
- `benchmark-full` (all) + `benchmark-full-tau2` / `-swebench` / `-skillsbench`.

### `.github/workflows/benchmarks.yml` (name stays `Benchmarks`)
- Matrix → `tier: [smoke, full]` × bench.
- New `workflow_dispatch` input **`tier`** (`all` / `smoke` / `full`, default **`smoke`**) so a
  manual run doesn't accidentally launch expensive full.
- Job `if` (PR): any label containing `benchmark-smoke` **or** `benchmark-full`.
- **Generalized gate** (tier-agnostic):
  - `workflow_dispatch`: run if (`tier` input is `all` or `== matrix.tier`) AND (`benchmark`
    input is `all` or `== matrix.bench`).
  - `pull_request`: run if labels contain `format('benchmark-{0}', matrix.tier)` **or**
    `format('benchmark-{0}-{1}', matrix.tier, matrix.bench)`.

### Scripts
- `run_suite.sh`: `BASE=ci/benchmarks/<bench>/${TIER:-smoke}`; **skip a task whose frozen
  baseline is missing** (warn, don't fail) — a partially-populated full tier runs what's ready.
- `freeze_baseline.sh`: `TIER` env (default smoke) → writes `<bench>/<tier>/<task>/baseline/`
  and nests `baselines.json` under the tier.
- `run_task.sh`: **unchanged** — it receives the (already tier-aware) frozen dir from run_suite.
- `select_tasks.sh`: unchanged; document that `TIER` selects where a later freeze writes.

### No change needed
- History page (Type column + `full` filter already shipped in #80) and `record.py`
  (tier already flows through). Records already carry `tier` from the runmeta step.

## Not in this PR (needs runner + budget)
- The actual `full/tasks.json` contents and frozen baselines (populate on skillberry-1 via
  `select_tasks.sh` → `freeze_baseline.sh` with `TIER=full`).

## Testing
- `run_suite.sh` / `freeze_baseline.sh` pass `bash -n`; `benchmarks.yml` YAML-lints with
  `tier:[smoke,full]` and the `tier` dispatch input.
- Reason through the gate truth table for smoke/full × dispatch/PR-label combos.
- `record.py` tests still pass (unchanged).
- Confirm the smoke migration didn't break paths: `run_suite.sh` with `TIER=smoke` resolves
  `<bench>/smoke/tasks.json` and the existing frozen baselines.
