# cost-030-threshold-not-an-anomaly

<!-- BEGIN:auto -->

**task:** `cost-030-threshold-not-an-anomaly`  
**category:** cost  
**tranche:** regression  
**services:** cost  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cost-030-threshold-not-an-anomaly/run_20260919_183407` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.953 |
| seed (val, v4_t2_e1) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.047

**T2 cost/time:** $1.39, 396,441 tokens, 0.32h (eval $1.39/396,441tok · optimizer $0.00/0tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cost-030-threshold-not-an-anomaly/run_20260919_183407/report.md`, `.capevolve/v4_t2_e1_cost-030-threshold-not-an-anomaly/run_20260919_183407/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A cost-monitor alert fired for an account, and the task is to decide whether it's a real anomaly before anyone opens an incident. The trap is the baseline: comparing against last month makes the spend look like a 2.5x jump, but comparing against the same month a year earlier shows it's an ordinary 5% seasonal increase -- so the task measures whether the agent checks the year-over-year baseline rather than stopping at month-over-month.

T2 ran the optimizer on this task, but no candidate beat the seed bundle on validation (`best_tag: "seed"`) -- see `.capevolve/v4_t2_e1_cost-030-threshold-not-an-anomaly/run_20260919_183407/report.md` and `.capevolve/v4_t2_e1_cost-030-threshold-not-an-anomaly/run_20260919_183407/JOURNAL.md` in the `parsec-intake_v4` worktree (not committed here) for what it tried. `final` above is the seed's own held-out test measurement, not a fallback.
