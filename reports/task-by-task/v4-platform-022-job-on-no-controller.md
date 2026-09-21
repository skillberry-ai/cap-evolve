# platform-022-job-on-no-controller

<!-- BEGIN:auto -->

**task:** `platform-022-job-on-no-controller`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.700 |
| our baseline (v4_t1_e1) | test | 3 | 0.700 |
| seed (val, v4_t2_e1) | val | 5 | 0.595 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.895 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.930 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.300 · delta vs our baseline: 0.300

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840/report.md`, `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
