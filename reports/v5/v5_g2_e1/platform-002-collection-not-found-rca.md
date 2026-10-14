# platform-002-collection-not-found-rca

<!-- BEGIN:auto -->

**task:** `platform-002-collection-not-found-rca`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.747 |
| v5_b1_e1 (original skill) | val | 5 | 0.837 |

per-trial rewards: [0.883, 0.883, 0.317, 0.767, 0.883]  
min 0.317 · max 0.883 · spread 0.567 · sd 0.220 · errored trials 0  
delta vs v5_b1_e1: -0.090  

**cost/time:** $0.3637, 106,710 tokens, 22.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.090** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
