# cloud-024-guid-to-account

<!-- BEGIN:auto -->

**task:** `cloud-024-guid-to-account`  
**category:** cloud  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** yes  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 1.000 |
| v5_b1_e1 (original skill) | val | 5 | 0.200 |

per-trial rewards: [1.000, 1.000, 1.000, 1.000, 1.000]  
min 1.000 · max 1.000 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: +0.800  

**cost/time:** $0.3678, 116,320 tokens, 8.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.800** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
