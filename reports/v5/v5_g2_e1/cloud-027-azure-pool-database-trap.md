# cloud-027-azure-pool-database-trap

<!-- BEGIN:auto -->

**task:** `cloud-027-azure-pool-database-trap`  
**category:** cloud  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.940 |
| v5_b1_e1 (original skill) | val | 5 | 1.000 |

per-trial rewards: [0.850, 1.000, 1.000, 1.000, 0.850]  
min 0.850 · max 1.000 · spread 0.150 · sd 0.073 · errored trials 0  
delta vs v5_b1_e1: -0.060  

**cost/time:** $0.8773, 283,555 tokens, 8.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.060 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
