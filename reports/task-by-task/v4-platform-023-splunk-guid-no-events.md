# platform-023-splunk-guid-no-events

<!-- BEGIN:auto -->

**task:** `platform-023-splunk-guid-no-events`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.933 |
| seed (val, v4_t2_e1) | val | 5 | 0.960 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.067

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/report.md`, `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
