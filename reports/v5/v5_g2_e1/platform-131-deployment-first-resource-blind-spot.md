# platform-131-deployment-first-resource-blind-spot

<!-- BEGIN:auto -->

**task:** `platform-131-deployment-first-resource-blind-spot`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.860 |
| v5_b1_e1 (original skill) | val | 5 | 0.944 |

per-trial rewards: [0.860, 0.720, 1.000, 0.860, 0.860]  
min 0.720 · max 1.000 · spread 0.280 · sd 0.089 · errored trials 0  
delta vs v5_b1_e1: -0.084  

**cost/time:** $1.4644, 468,853 tokens, 11.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.084 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
