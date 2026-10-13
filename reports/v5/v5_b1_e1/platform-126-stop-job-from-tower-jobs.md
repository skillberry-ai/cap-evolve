# platform-126-stop-job-from-tower-jobs

<!-- BEGIN:auto -->

**task:** `platform-126-stop-job-from-tower-jobs`  
**category:** platform  
**task set:** 10-12  
**status:** ok  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.850 |

per-trial rewards: [0.850, 0.850, 0.850, 0.850, 0.850]  
min 0.850 · max 0.850 · spread 0.000 · sd 0.000 · errored trials 0

**cost/time:** $0.6489, 204,234 tokens, 5.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 44 of 136 v5 tasks are deterministic.

This task came from the **`v5_2026-10-12`** drop (the second 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
