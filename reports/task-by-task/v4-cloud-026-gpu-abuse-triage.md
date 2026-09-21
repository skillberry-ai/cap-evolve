# cloud-026-gpu-abuse-triage

<!-- BEGIN:auto -->

**task:** `cloud-026-gpu-abuse-triage`  
**category:** cloud  
**tranche:** regression  
**services:** cloud  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.808 |
| our baseline (v4_t1_e1) | test | 3 | 0.886 |
| seed (val, v4_t2_e1) | val | 5 | 0.940 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.907 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.977 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.192 · delta vs our baseline: 0.114

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620/report.md`, `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620/JOURNAL.md`

<!-- END:auto -->

_Not yet analysed._
