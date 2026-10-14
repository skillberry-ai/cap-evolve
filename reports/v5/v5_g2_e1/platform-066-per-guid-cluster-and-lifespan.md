# platform-066-per-guid-cluster-and-lifespan

<!-- BEGIN:auto -->

**task:** `platform-066-per-guid-cluster-and-lifespan`  
**category:** platform  
**task set:** 10-10  
**origin:** new-10-10  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.965 |
| v5_b1_e1 (original skill) | val | 5 | 1.000 |

per-trial rewards: [0.912, 1.000, 1.000, 1.000, 0.912]  
min 0.912 · max 1.000 · spread 0.087 · sd 0.043 · errored trials 0  
delta vs v5_b1_e1: -0.035  

**cost/time:** $0.9791, 297,843 tokens, 12.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.035 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-10` drop -- `cand_0004` was never tuned against it.
