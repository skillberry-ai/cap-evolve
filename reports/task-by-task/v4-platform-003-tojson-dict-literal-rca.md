# platform-003-tojson-dict-literal-rca

<!-- BEGIN:auto -->

**task:** `platform-003-tojson-dict-literal-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.233 |
| our baseline (v4_t1_e1) | test | 3 | 0.478 |
| seed (val, v4_t2_e1) | val | 5 | 0.563 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.847 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.917 |
| final (test, v4_t2_e1) | test | 5 | 0.763 |

delta vs JB: 0.530 · delta vs our baseline: 0.286

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/report.md`, `.capevolve/v4_t2_e1_platform-003-tojson-dict-literal-rca/run_20260920_054127/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
