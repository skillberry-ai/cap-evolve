# icinga-014-check-script-path-moved

<!-- BEGIN:auto -->

**task:** `icinga-014-check-script-path-moved`  
**category:** icinga  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.515 |
| v5_b1_e1 (original skill) | val | 5 | 0.515 |

per-trial rewards: [0.550, 0.550, 0.550, 0.375, 0.550]  
min 0.375 · max 0.550 · spread 0.175 · sd 0.070 · errored trials 0  
delta vs v5_b1_e1: +0.000  

**cost/time:** $1.4289, 448,931 tokens, 9.9 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.000 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
