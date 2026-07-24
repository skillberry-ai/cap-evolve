# Benchmark CI History Page — Design

**Date:** 2026-07-23
**Status:** Approved design, pre-implementation
**Branch:** `feat/benchmark-history-page`

## Problem

The `ci/benchmarks` suite (tau2 · swebench · skillsbench) runs on demand — on PRs via the
`benchmark-test` label and manually via `workflow_dispatch`. Today each run's results are
**ephemeral**: they exist only as (a) a sticky PR comment, (b) an Actions artifact that
expires (~90 days), and (c) transient files on the self-hosted runner. There is **no durable,
aggregated record** of benchmark executions over time, and nothing on the public site
(`https://skillberry-ai.github.io/cap-evolve/`) that shows the running history.

## Goal

Collect the results of **every** CI benchmark execution — PR runs and manual (`workflow_dispatch`)
runs, whole-suite or single-benchmark — into a durable store, and publish them on the GitHub
Pages site as a **sortable, filterable HTML table** with per-benchmark rollup rows that expand
to per-task detail.

## Scope decisions (confirmed with maintainer)

- **Forward-only** collection. No historical backfill (past PR runs were mostly `skipped`, and
  artifacts expire). The page starts sparse and grows as runs happen.
- **Row granularity: both** — per-`(run × benchmark)` rollup rows that **expand** to show the
  per-task detail rows.
- **Persistence + delivery: Approach 1** — a dedicated `benchmark-history` orphan branch written
  by a single aggregator job; the static page fetches the aggregated JSON at runtime from
  `raw.githubusercontent.com`. Keeps `main` history clean; the page is always fresh with no
  redeploy.

## Non-goals

- No backfill of expired/`skipped` past runs.
- No new server or database; no build step / JS framework (the site is static HTML/CSS today).
- Not a replacement for the curated `site/results.html` (canonical, hand-verified numbers) or
  the separate `dashboard/` app. This is a **raw log of CI executions**, a distinct page.
- No change to *what* the benchmark suite measures or how it scores.

## Data model

One record per **(run × benchmark)**, so partial suites and manual runs slot in naturally.

```jsonc
{
  "schema": 1,
  "run_id": 30013033262,
  "run_url": "https://github.com/skillberry-ai/cap-evolve/actions/runs/30013033262",
  "bench": "tau2",                     // tau2 | swebench | skillsbench
  "event": "pull_request",             // pull_request | workflow_dispatch
  "source": "PR #55",                  // human label: "PR #55" or "manual (main)"
  "pr": 55,                            // null for manual runs
  "branch": "feature/skill-tool-optimization-knowledge",
  "sha": "abc1234",
  "date": "2026-07-23T13:50:51Z",      // run createdAt (UTC ISO-8601)
  "iterations": 1,
  "agent_model": "aws/gpt-oss-120b",
  "optimizer_model": "claude-opus-4-8",
  "conclusion": "success",             // success | failure | cancelled — surfaces failed jobs
  "suite": {                           // rollup (null when conclusion != success / no metrics)
    "reward_base": 0.0, "reward_opt": 0.0,
    "flips": 0, "n": 2, "optimizer_usd": 0.12
  },
  "tasks": [                           // one object per task; exactly the metrics.py `extract` shape
    { "bench": "tau2", "task": "35", "reward_baseline": 0.0, "reward_opt": 0.0,
      "reward_delta": 0.0, "flipped": false,
      "latency_baseline_s": 12.3, "latency_opt_s": 13.1,
      "cost_baseline_usd": 0.0, "cost_opt_runner_usd": 0.0,
      "optimizer_usd": 0.06, "optimizer_tokens": 0, "optimizer_seconds": 0, "iterations": 1 }
  ]
}
```

Aggregated artifacts on the `benchmark-history` branch:

- `records/<run_id>__<bench>.json` — one file per record (immutable; unique name → no write races).
- `benchmarks.json` — array of all records (what the page fetches).
- `meta.json` — `{ "updated": "<ISO>", "count": <n>, "runs": <n_runs> }` for a "last updated" line.

## Components (each single-purpose, independently testable)

1. **`ci/benchmarks/lib/record.py`**
   - `build_record(metrics_jsonl_path, meta: dict) -> dict` — pure function: reads a suite's
     `metrics.jsonl`, computes the `suite` rollup (reuse the same math as `metrics.py table`),
     merges run metadata, returns one record dict. No I/O beyond reading the given file.
   - `main()` CLI: `record.py build <metrics.jsonl> --bench B --meta meta.json > record.json`,
     reading run metadata from a small JSON (so the workflow passes `$GITHUB_*` values in).
   - Unit tests: rollup math, partial suite, failed-run (no metrics) → `suite: null`,
     manual-vs-PR `source` labelling.

2. **`aggregate` job** in `.github/workflows/benchmarks.yml`
   - `needs: [bench]`, `if: always()` (so it records failed bench jobs too),
     `runs-on: ubuntu-latest` (GitHub-hosted is fine — it only shuffles JSON + git, no VPC).
   - Downloads the 3 `benchmarks-<bench>` artifacts (each already contains `metrics.jsonl`;
     add the per-job `conclusion` via the jobs API or matrix outputs).
   - For each present bench: `record.py build …` → `records/<run_id>__<bench>.json`.
   - Checks out the orphan `benchmark-history` branch (create if missing), writes the record
     files, regenerates `benchmarks.json` (glob `records/*.json`) + `meta.json`, commits, and
     **pushes once** (single writer → no races between the matrix jobs).
   - Uses the default `GITHUB_TOKEN` with `permissions: contents: write` scoped to the job.

3. **`benchmark-history` orphan branch** — data only, no source tree. Created once (bootstrap
   documented in `ci/benchmarks/README.md`).

4. **`site/benchmarks.html` + `site/benchmarks.js`** — vanilla JS, reusing the existing nav +
   `style.css`. Adds a "Benchmark runs" nav link. On load, fetches
   `https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history/benchmarks.json`
   (public repo → CORS-OK) with a `?t=<timestamp>` cache-buster (raw.githubusercontent has a
   ~5 min CDN cache), renders the table, wires client-side sort/filter/expand. Shows the
   `meta.json` "last updated" line and a graceful empty/error state.

## Page UX

- **Rollup rows** (one per run×bench): source (PR link or "manual"), date, bench, iters,
  mean reward `base→opt`, flips `x/n`, optimizer `$`, conclusion badge (green success /
  red failure / grey cancelled). Click to **expand** the per-task detail table.
- **Sort:** click any column header (date default, newest first).
- **Filter:** benchmark (tau2/swebench/skillsbench), source (PR / manual), conclusion, date
  range, and a free-text search over branch + task id.
- Failed/cancelled runs appear as rows with a red/grey badge and no metrics — so infra failures
  are visible in the log, not silently dropped.
- Pure client-side (data volume is small); no dependencies beyond the one `benchmarks.js` file.

## Data flow

```
bench job (self-hosted)  →  metrics.jsonl + artifact
        │
        ▼
aggregate job (ubuntu, needs:[bench], if:always)
   record.py → records/<run_id>__<bench>.json
   regenerate benchmarks.json + meta.json
   commit + push (single writer) → benchmark-history branch
        │
        ▼
site/benchmarks.html  (fetches benchmarks.json at load) → sort / filter / expand
```

New benchmark data needs **no Pages redeploy**; the page HTML deploys once via the existing
`pages.yml` when `site/**` changes.

## Error handling

- **Failed/cancelled bench job:** aggregator still writes a record (`conclusion` set, `suite: null`);
  the page shows it as a failed run. `if: always()` on the aggregate job ensures this.
- **Missing/empty `metrics.jsonl`:** `record.py` yields `suite: null, tasks: []` rather than crashing.
- **Concurrent runs:** single aggregate writer per run; distinct `records/*` filenames; the push
  uses a fetch+rebase-retry loop to tolerate a second run's aggregate landing between fetch and push.
- **Page fetch failure / empty history:** the page renders an explicit "no runs yet" / "couldn't
  load" state instead of a blank table.
- **Orphan branch missing:** aggregator bootstraps it (`git checkout --orphan`) on first run.

## Testing

- Unit: `record.py` rollup math, partial suite, failed-run, PR-vs-manual `source`
  (mirrors existing `ci/benchmarks/lib` test style).
- Fixture: a sample `metrics.jsonl` → expected `record.json` (golden file).
- Aggregation: `benchmarks.json` regeneration from a `records/` fixture dir (idempotent; stable order).
- Page: a tiny local fixture `benchmarks.json` to eyeball sort/filter/expand + empty/error states
  before wiring the live URL.
- Workflow: dry-run the `aggregate` job logic locally against downloaded artifacts before merge.

## Rollout

1. Land page + `record.py` + `aggregate` job on this branch; bootstrap the `benchmark-history`
   branch (empty `benchmarks.json`).
2. Merge to `main`; `pages.yml` deploys `benchmarks.html`.
3. Next labelled/dispatched benchmark run populates the history; verify the page updates.
