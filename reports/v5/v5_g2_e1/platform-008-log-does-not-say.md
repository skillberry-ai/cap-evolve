# platform-008-log-does-not-say

<!-- BEGIN:auto -->

**task:** `platform-008-log-does-not-say`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.920 |
| v5_b1_e1 (original skill) | val | 5 | 0.960 |

per-trial rewards: [1.000, 1.000, 0.600, 1.000, 1.000]  
min 0.600 · max 1.000 · spread 0.400 · sd 0.160 · errored trials 0  
delta vs v5_b1_e1: -0.040  

**cost/time:** $0.3370, 100,770 tokens, 16.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.040 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
