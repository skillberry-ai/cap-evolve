# icinga-208-service-not-monitored

<!-- BEGIN:auto -->

**task:** `icinga-208-service-not-monitored`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.680 |
| v5_b1_e1 (original skill) | val | 5 | 0.800 |

per-trial rewards: [0.800, 0.600, 0.600, 0.600, 0.800]  
min 0.600 · max 0.800 · spread 0.200 · sd 0.098 · errored trials 0  
delta vs v5_b1_e1: -0.120  

**cost/time:** $0.7045, 222,680 tokens, 6.6 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.120** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
