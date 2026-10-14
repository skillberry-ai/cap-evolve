# platform-022-job-on-no-controller

<!-- BEGIN:auto -->

**task:** `platform-022-job-on-no-controller`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.930 |
| v5_b1_e1 (original skill) | val | 5 | 0.700 |

per-trial rewards: [0.825, 0.825, 1.000, 1.000, 1.000]  
min 0.825 · max 1.000 · spread 0.175 · sd 0.086 · errored trials 0  
delta vs v5_b1_e1: +0.230  

**cost/time:** $0.2734, 81,560 tokens, 5.6 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.230** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
