# platform-033-schema-change-not-the-oom

<!-- BEGIN:auto -->

**task:** `platform-033-schema-change-not-the-oom`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.752 |
| v5_b1_e1 (original skill) | val | 5 | 0.829 |

per-trial rewards: [0.488, 0.381, 1.000, 0.893, 1.000]  
min 0.381 · max 1.000 · spread 0.619 · sd 0.265 · errored trials 0  
delta vs v5_b1_e1: -0.076  

**cost/time:** $1.9986, 638,545 tokens, 17.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.076 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
