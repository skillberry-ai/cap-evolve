# cost-407-aws-historical-query-came-back-org-wide

<!-- BEGIN:auto -->

**task:** `cost-407-aws-historical-query-came-back-org-wide`  
**category:** cost  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** yes  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.600 |
| v5_b1_e1 (original skill) | val | 5 | 0.600 |

per-trial rewards: [0.600, 0.600, 0.600, 0.600, 0.600]  
min 0.600 · max 0.600 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: +0.000  

**cost/time:** $0.4955, 157,640 tokens, 3.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.000 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
