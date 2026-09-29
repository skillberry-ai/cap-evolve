# parsec v4

**Spec:** `docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` (branch `parsec-v4-docs`)

v4 runs hill-climb optimization over the same 34 `parsec34` tasks (4 categories: platform, icinga,
cloud, cost) starting from the same shared 8-file multi-agent bundle (`artifacts/v4/seed/`), varying
only the *scope* at which the optimizer edits that bundle. Two arms have run so far:

## Shared setup

- **Task set:** all 34 v4 tasks, same 4 categories, same `regression`/`challenge` tranche split as
  every other v4 arm.
- **Agent model:** `claude-sonnet-4-6` (both arms).
- **Optimizer model:** `claude-opus-5`, via `optimizer_skill: claude-code`, `algorithm_skill:
  hill-climb`, `capabilities: [system-prompt]`, `num_trials: 5` (both arms).
- **Seed bundle:** `artifacts/v4/seed/`, byte-identical between arms — both hill-climb from the same
  starting point.
- **Split discipline:** no independent holdout this phase — `train == val == test` for both arms,
  at different scales (one task for T, all 34 for G). See each arm's recipe README.
- **Budget differs per arm** — T's is per-task and small (`max_usd: 50.0` per task); G's is a single
  run-wide budget an order of magnitude larger (`max_usd: 1000.0`). See each arm's `summary.md` for
  exact values.

## The two arms

| arm | scope | result | links |
|---|---|---|---|
| **T** (`v4_t_e1`) | task-by-task: one optimizer loop per task | T2 raises mean reward on both tranches over 21/34 tasks; T4's static merge of those bundles regresses 8 tasks | [`summary.md`](v4_t_e1/summary.md) · [`results.json`](v4_t_e1/results.json) · [`cost_time/`](v4_t_e1/cost_time/) · [heatmap](../../ui/heatmap_v4_t_e1.html) · [artifacts](../../artifacts/v4/v4_t_e1/) · [recipe](../../recipes/v4/v4_t_e1/) · [reports](../../reports/v4/v4_t_e1/) |
| **G** (`v4_g_e1`) | global: one shared bundle evolved jointly across all 34 tasks | +0.0946 all-tasks mean reward over baseline after 6 iterations (run stopped, not a clean budget exhaustion) | [`summary.md`](v4_g_e1/summary.md) · [`results.json`](v4_g_e1/results.json) · [`cost_time/`](v4_g_e1/cost_time/) · [heatmap](../../ui/heatmap_v4_g_e1.html) · [artifacts](../../artifacts/v4/v4_g_e1/) · [recipe](../../recipes/v4/v4_g_e1/) · [reports](../../reports/v4/v4_g_e1/) |

See [`comparison.md`](comparison.md) for the T-vs-G head-to-head.

## What hasn't run

- **T3** (transfer) — spec §2 describes it but it isn't designed yet: one task's T2 bundle,
  evaluated zero-shot on a different task.
- **T5** — continued joint optimization after T4's merge, which would get a chance to self-correct
  the 8 regressions T4 introduced.
- **C2-C4** (category-scoped arms) — designed in the spec (§2) but not submitted.

**C1/G1 need no separate job.** They're derived directly from T1's `our_baseline` column
(`sections.category`/`sections.global` in `v4_t_e1/results.json`), computed by
`build_v4_t_results_json.py` — not a standalone run, so don't go looking for one.

## Next move: CCC/LSF migration

Running T5/C2-C4's jobs on CCC/LSF in parallel is deferred until this local restructuring work (this
PR and the recipe/artifact/report changes alongside it) is committed and pushed (spec §7).
