# platform-001-ee-entrypoint-rca

<!-- BEGIN:auto -->

**task:** `platform-001-ee-entrypoint-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.520 |
| our baseline (v4_t1_e1) | test | 3 | 0.713 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.940 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.952 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.480 · delta vs our baseline: 0.287

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/report.md`, `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
