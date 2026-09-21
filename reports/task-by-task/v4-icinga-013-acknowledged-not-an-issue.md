# icinga-013-acknowledged-not-an-issue

<!-- BEGIN:auto -->

**task:** `icinga-013-acknowledged-not-an-issue`  
**category:** icinga  
**tranche:** regression  
**services:** icinga  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.480 |
| our baseline (v4_t1_e1) | test | 3 | 0.373 |
| seed (val, v4_t2_e1) | val | 5 | 0.448 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.608 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.000 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.640 |
| final (test, v4_t2_e1) | test | 5 | 0.640 |

delta vs JB: 0.160 · delta vs our baseline: 0.267

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/report.md`, `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
