# parsec v5

v5 is a **from-scratch, physically isolated rebuild** of the parsec benchmark material: new task
copies under a renamed `bench-v5-` prefix, 68 tasks total (4 categories: platform, icinga, cloud,
cost), no shared code or content with any v4/h4 worktree. It exists because v4's own 34-task set
and h4's 30-task held-out set were both found, during setup, to have drifted from the copies this
repo's v4/h4 arms were built against — rather than reconcile that lineage, this benchmark starts
clean, with logic and parameters kept identical to what was proven to work for v4/h4.

## Shared setup

- **Task set:** all 68 v5 tasks. 34 share a byte-identical task id with v4's original 34-task set;
  21 more match an h4 held-out task id; 2 kept a task number but got different content
  (`origin: "renamed-content-changed"` in each arm's ledger); 11 are brand new.
- **Agent model:** `claude-sonnet-4-6`.
- **Seed bundle:** `artifacts/v5/seed/` — **not** byte-identical to `artifacts/v4/seed/` (confirmed
  diff: the shared `orchestrator.md` picked up unrelated routing-logic changes between the two
  snapshot dates). See each arm's summary for what this means for cross-arm deltas.

## Arms run so far

| arm | scope | result | links |
|---|---|---|---|
| **v5_t1_e1** | T1 (original skill), zero-shot, no optimization, all 68 tasks | mean reward 0.8885, 0 errored trials; +0.122 over the pooled matched-task prior-arm mean (not a controlled A/B — see summary) | [`summary.md`](v5_t1_e1/summary.md) · [`results.json`](v5_t1_e1/results.json) · [`cost_time/`](v5_t1_e1/cost_time/) · [heatmap](../../ui/heatmap_v5_t1_e1.html) · [artifacts](../../artifacts/v5/seed/) · [recipe](../../recipes/v5/v5_t1_e1/) · [reports](../../reports/v5/v5_t1_e1/) |

See [`../../reports/v5-vs-v4-h4-comparison.md`](../../reports/v5-vs-v4-h4-comparison.md) for the
full task-by-task cross-benchmark comparison.

## What hasn't run

No optimizer arm (v5's own T2/G equivalent) has run yet — v5_t1_e1 is a baseline only, matching the
role v4_t4_e1/e2 play for v4 rather than v4_t_e1/v4_g_e1.

## Open items

- `icinga-072-alert-output-not-decoy-metrics` scored a genuine 0.0 (not an infra error) — flagged,
  not yet investigated.
- Whether to pin `artifacts/v5/seed/` to a byte-identical copy of `artifacts/v4/seed/` and re-run,
  to get a controlled A/B before trusting the matched-task deltas as more than orientation.
