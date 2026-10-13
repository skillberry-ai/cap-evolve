# parsec v5

v5 is a **from-scratch rebuild** of the parsec benchmark material: new task copies under a
`bench-v5-` prefix, **136 tasks** pooled from two independently authored 68-task drops
(`v5_2026-10-10` and `v5_2026-10-12`), 4 categories (platform, icinga, cloud, cost), no shared
content with any v4/h4 tree.

It exists because v4's own 34-task set and h4's 30-task held-out set were both found to have
drifted from the copies this branch's v4/h4 arms were built against (different `golden.json`,
seeds, `verify.py`). Rather than reconcile that lineage, v5 starts clean, with logic and
parameters kept identical to what was proven for v4/h4.

## Shared setup

- **Task set:** all 136 v5 tasks. Per-task drop membership is recorded in each arm's ledger
  (`task_set`: `10-10` or `10-12`); the two drops are statistically indistinguishable in
  difficulty (permutation p = 0.62 — see the baseline arm's summary).
- **Agent model:** `claude-sonnet-4-6`.
- **Skill under test (baseline):** [`../../artifacts/v5/seed/`](../../artifacts/v5/seed/) —
  verified byte-identical (8/8 prompt files) to parsec commit `28e2c40` and to
  [`../../artifacts/v4/seed/`](../../artifacts/v4/seed/). **Verify the artifact under test against
  a known commit before running an arm**; see the baseline summary for the run this rule was
  learned from.

## Arms run so far

| arm | scope | result | links |
|---|---|---|---|
| **b1** (`v5_b1_e1`) | baseline: original skill, zero-shot, no optimization, all 136 tasks | mean reward **0.7260**, 0 errored trials; 30/136 saturated; **68% of tasks non-deterministic** | [`summary.md`](v5_b1_e1/summary.md) · [`results.json`](v5_b1_e1/results.json) · [`cost_time/`](v5_b1_e1/cost_time/) · [heatmap](../../ui/heatmap_v5_b1_e1.html) · [per-trial](../../ui/trials_v5_b1_e1.html) · [recipe](../../recipes/v5/v5_b1_e1/) · [reports](../../reports/v5/v5_b1_e1/) |

Naming: `b` = baseline, `t` = task-by-task optimization, `g` = global (shared-bundle)
optimization — so `v5_b1_e1` is the first baseline experiment, and the planned optimizer arms are
`v5_t*_e*` / `v5_g*_e*`.

## What hasn't run

No optimizer arm yet. The plan is to split the 136 randomly into a train half (`o5`) and a
held-out half (`h5`), run the task-by-task and global arms on `o5`, and validate on `h5`. The
baseline's permutation test is what licenses a random split rather than a drop-based one.

## Open items before the optimizer arms

- **Gating rule.** 68% of tasks are non-deterministic; a per-task delta below ~0.25 is
  indistinguishable from noise at n=5, while the suite mean resolves to ~0.02. A hill-climb gate
  accepting on any per-task gain will accept noise. See the baseline summary's noise-floor section.
- **Trial timeouts are not enforced end-to-end** — two baseline tasks hung ~6.5h below the
  adapter's 20-minute cap. Worth fixing before arms that run far more trials.
- **Two deterministic zeros** (`cloud-304-marketplace-active-past-end`,
  `icinga-072-alert-output-not-decoy-metrics`) — real capability gap or contract defect, unexamined.
