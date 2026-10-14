# cloud-309-deleted-iam-user-trail-remains

<!-- BEGIN:auto -->

**task:** `cloud-309-deleted-iam-user-trail-remains`  
**category:** cloud  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.736 |
| v5_b1_e1 (original skill) | val | 5 | 0.782 |

per-trial rewards: [0.689, 0.767, 0.767, 0.767, 0.689]  
min 0.689 · max 0.767 · spread 0.078 · sd 0.038 · errored trials 0  
delta vs v5_b1_e1: -0.047  

**cost/time:** $1.2375, 375,655 tokens, 11.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.047 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
