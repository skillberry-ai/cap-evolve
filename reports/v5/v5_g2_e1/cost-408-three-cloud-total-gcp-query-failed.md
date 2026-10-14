# cost-408-three-cloud-total-gcp-query-failed

<!-- BEGIN:auto -->

**task:** `cost-408-three-cloud-total-gcp-query-failed`  
**category:** cost  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.608 |
| v5_b1_e1 (original skill) | val | 5 | 0.664 |

per-trial rewards: [0.720, 0.580, 0.580, 0.580, 0.580]  
min 0.580 · max 0.720 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: -0.056  

**cost/time:** $0.7428, 229,044 tokens, 8.5 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.056 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
