# cost-403-capacity-results-truncated-at-50

<!-- BEGIN:auto -->

**task:** `cost-403-capacity-results-truncated-at-50`  
**category:** cost  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.904 |
| v5_b1_e1 (original skill) | val | 5 | 0.840 |

per-trial rewards: [0.840, 1.000, 0.840, 0.840, 1.000]  
min 0.840 · max 1.000 · spread 0.160 · sd 0.078 · errored trials 0  
delta vs v5_b1_e1: +0.064  

**cost/time:** $0.5808, 179,992 tokens, 5.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.064 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
