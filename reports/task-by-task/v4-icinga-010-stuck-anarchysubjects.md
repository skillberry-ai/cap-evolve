# icinga-010-stuck-anarchysubjects

<!-- BEGIN:auto -->

**task:** `icinga-010-stuck-anarchysubjects`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.495 |
| our baseline (v4_t1_e1) | test | 3 | 0.402 |
| seed (val, v4_t2_e1) | val | 5 | 0.467 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.495 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.495 |
| final (test, v4_t2_e1) | test | 5 | 0.495 |

delta vs JB: 0.000 · delta vs our baseline: 0.093

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/report.md`, `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
