# icinga-010-stuck-anarchysubjects

<!-- BEGIN:auto -->

**task:** `icinga-010-stuck-anarchysubjects`  
**category:** icinga  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.523 |
| v5_b1_e1 (original skill) | val | 5 | 0.495 |

per-trial rewards: [0.495, 0.495, 0.495, 0.635, 0.495]  
min 0.495 · max 0.635 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: +0.028  

**cost/time:** $1.7441, 543,407 tokens, 17.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.028 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
