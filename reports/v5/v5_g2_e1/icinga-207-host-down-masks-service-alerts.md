# icinga-207-host-down-masks-service-alerts

<!-- BEGIN:auto -->

**task:** `icinga-207-host-down-masks-service-alerts`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.833 |
| v5_b1_e1 (original skill) | val | 5 | 0.867 |

per-trial rewards: [0.833, 0.750, 0.917, 0.833, 0.833]  
min 0.750 · max 0.917 · spread 0.167 · sd 0.053 · errored trials 0  
delta vs v5_b1_e1: -0.033  

**cost/time:** $0.5538, 173,397 tokens, 5.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.033 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
