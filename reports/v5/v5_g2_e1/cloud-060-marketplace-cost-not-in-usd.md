# cloud-060-marketplace-cost-not-in-usd

<!-- BEGIN:auto -->

**task:** `cloud-060-marketplace-cost-not-in-usd`  
**category:** cloud  
**task set:** 10-10  
**origin:** renamed-content-changed  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.240 |
| v5_b1_e1 (original skill) | val | 5 | 0.280 |

per-trial rewards: [0.200, 0.400, 0.200, 0.200, 0.200]  
min 0.200 · max 0.400 · spread 0.200 · sd 0.080 · errored trials 0  
delta vs v5_b1_e1: -0.040  

**cost/time:** $0.6937, 219,965 tokens, 7.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.040 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** kept a v4/h4 task number but has different content; `cand_0004` was never tuned against this content.
