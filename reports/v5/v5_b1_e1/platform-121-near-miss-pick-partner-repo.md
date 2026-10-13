# platform-121-near-miss-pick-partner-repo

<!-- BEGIN:auto -->

**task:** `platform-121-near-miss-pick-partner-repo`  
**category:** platform  
**task set:** 10-12  
**status:** ok  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.500 |

per-trial rewards: [0.500, 0.500, 0.500, 0.500, 0.500]  
min 0.500 · max 0.500 · spread 0.000 · sd 0.000 · errored trials 0

**cost/time:** $1.7119, 552,722 tokens, 12.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 44 of 136 v5 tasks are deterministic.

This task came from the **`v5_2026-10-12`** drop (the second 68). The two drops are statistically indistinguishable in difficulty (permutation p = 0.62) -- see [`../../../results/v5/v5_b1_e1/summary.md`](../../../results/v5/v5_b1_e1/summary.md).
