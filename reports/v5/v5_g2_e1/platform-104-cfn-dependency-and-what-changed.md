# platform-104-cfn-dependency-and-what-changed

<!-- BEGIN:auto -->

**task:** `platform-104-cfn-dependency-and-what-changed`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.840 |
| v5_b1_e1 (original skill) | val | 5 | 0.760 |

per-trial rewards: [0.700, 0.900, 0.900, 0.900, 0.800]  
min 0.700 · max 0.900 · spread 0.200 · sd 0.080 · errored trials 0  
delta vs v5_b1_e1: +0.080  

**cost/time:** $0.4707, 131,558 tokens, 36.3 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.080 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
