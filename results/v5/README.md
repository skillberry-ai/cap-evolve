# parsec v5

v5 is a **from-scratch rebuild** of the parsec benchmark material: new task copies under a
`bench-v5-` prefix, **136 tasks** pooled from two independently authored 68-task drops
(`v5_2026-10-10` and `v5_2026-10-12`), 4 categories (platform, icinga, cloud, cost), no shared
content with any v4/h4 tree.

It exists because v4's own 34-task set and h4's 30-task held-out set were both found to have
drifted from the copies this branch's v4/h4 arms were built against. Rather than reconcile that
lineage, v5 starts clean, with logic and parameters kept identical to what was proven for v4/h4.

## Shared setup

- **Task set:** all 136 v5 tasks. Each arm's ledger records, per task, its `task_set` (`10-10` /
  `10-12`) and its `origin`: `v4-34` (v4's original tasks, contracts unchanged), `h4-rewritten`
  (shares an h4 id but was rewritten — h4's numbers do not carry over), `renamed-content-changed`,
  or new.
- **Agent model:** `claude-sonnet-4-6`.
- **Skill under test (baseline):** [`../../artifacts/v5/seed/`](../../artifacts/v5/seed/) —
  verified byte-identical (8/8 prompt files) to parsec commit `28e2c40` and to
  [`../../artifacts/v4/seed/`](../../artifacts/v4/seed/).
- **Every trial is audited** against its on-disk record before its number is used. cap-evolve counts
  only the exceptions it catches itself; a harbor timeout reaches the ledger as a clean `0.0`.

## Arms

| arm | scope | result | links |
|---|---|---|---|
| **b1** (`v5_b1_e1`) | baseline: original skill, zero-shot, no optimization, all 136 tasks | mean reward **0.8114** from 679 audited trials; reproduces v4's original-skill baseline on the 34 shared tasks to **−0.002**; 56% of tasks vary across trials, min detectable per-task delta ~0.09 | [`summary.md`](v5_b1_e1/summary.md) · [`results.json`](v5_b1_e1/results.json) · [`cost_time/`](v5_b1_e1/cost_time/) · [heatmap](../../ui/heatmap_v5_b1_e1.html) · [per-trial](../../ui/trials_v5_b1_e1.html) · [recipe](../../recipes/v5/v5_b1_e1/) · [reports](../../reports/v5/v5_b1_e1/) |
| **g2** (`v5_g2_e1`) | v4's accepted G2-arm champion `cand_0004` reused as-is (no v5-specific optimization), all 136 tasks | mean reward **0.8323** (**+0.021** vs `b1`), but no group clears the ~0.09 noise floor — no significant change at the aggregate level despite 22 tasks up / 9 down beyond noise. Biggest group move: v4's own 34 tasks, +0.079 | [`summary.md`](v5_g2_e1/summary.md) · [`results.json`](v5_g2_e1/results.json) · [`cost_time/`](v5_g2_e1/cost_time/) · [heatmap](../../ui/heatmap_v5_g2_e1.html) · [per-trial](../../ui/trials_v5_g2_e1.html) · [recipe](../../recipes/v5/v5_g2_e1/) · [reports](../../reports/v5/v5_g2_e1/) |
| ~~`v5_t1_e1`~~ | **discarded** — 68 tasks run against `v4_g_e1/rejected/cand_0001` (a v4 global-optimizer candidate), not the original skill | not a baseline; recorded separately in PR #801 | — |

Naming: `b` = baseline, `t` = task-by-task optimization, `g` = global (shared-bundle) optimization.

## Before the optimizer arms

- **Grader defects.** 21 tasks penalise correct answers or demand an unshown vocabulary — see
  [`../../reports/v5-benchmark-quality-review.md`](../../reports/v5-benchmark-quality-review.md).
  Patch them, or exclude them from both halves of the split.
- **Split stratified, not purely random.** 10-10 outscores 10-12 by +0.074 (p = 0.06), about half
  of it from the 21 `h4-rewritten` tasks the original skill now finds easy. Stratify `o5`/`h5` by
  task set and category.
- **Gate with a margin.** A per-task delta below ~0.09 is noise at 5 trials; the suite mean
  resolves to ~0.02.
- **Infra:** gateway hangs before the first tool call are the dominant failure; one can leave a
  simulator call in flight that blocks the next trials' reseeding (`HTTP 409`). Audit every trial.
