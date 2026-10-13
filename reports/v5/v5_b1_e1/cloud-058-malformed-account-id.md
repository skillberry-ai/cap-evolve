# cloud-058-malformed-account-id

<!-- BEGIN:auto -->

**task:** `cloud-058-malformed-account-id`  
**category:** cloud  
**task set:** 10-10  
**status:** ok  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.600 |

per-trial rewards: [0.600, 0.600, 0.600, 0.600, 0.600]  
min 0.600 · max 0.600 · spread 0.000 · sd 0.000 · errored trials 0

**cost/time:** $0.1598, 51,397 tokens, 2.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 44 of 136 v5 tasks are deterministic.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
