# platform-101-vcpu-quota-from-catalog-sizing

<!-- BEGIN:auto -->

**task:** `platform-101-vcpu-quota-from-catalog-sizing`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.790 |
| v5_b1_e1 (original skill) | val | 5 | 0.593 |

per-trial rewards: [0.825, 0.738, 0.825, 0.738, 0.825]  
min 0.738 · max 0.825 · spread 0.087 · sd 0.043 · errored trials 0  
delta vs v5_b1_e1: +0.198  

**cost/time:** $1.2353, 384,422 tokens, 19.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.198** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
