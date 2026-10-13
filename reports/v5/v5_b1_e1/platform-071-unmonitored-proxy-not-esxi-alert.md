# platform-071-unmonitored-proxy-not-esxi-alert

<!-- BEGIN:auto -->

**task:** `platform-071-unmonitored-proxy-not-esxi-alert`  
**category:** platform  
**task set:** 10-10  
**status:** ok  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.383 |

per-trial rewards: [0.383, 0.383, 0.383, 0.383, 0.383]  
min 0.383 · max 0.383 · spread 0.000 · sd 0.000 · errored trials 0

**cost/time:** $1.2542, 378,102 tokens, 11.5 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 44 of 136 v5 tasks are deterministic.

This task came from the **`v5_2026-10-10`** drop (the first 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
