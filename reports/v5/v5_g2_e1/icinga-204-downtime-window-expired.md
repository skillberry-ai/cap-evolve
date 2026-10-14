# icinga-204-downtime-window-expired

<!-- BEGIN:auto -->

**task:** `icinga-204-downtime-window-expired`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.680 |
| v5_b1_e1 (original skill) | val | 5 | 0.700 |

per-trial rewards: [0.600, 0.700, 0.700, 0.700, 0.700]  
min 0.600 · max 0.700 · spread 0.100 · sd 0.040 · errored trials 0  
delta vs v5_b1_e1: -0.020  

**cost/time:** $0.5464, 170,371 tokens, 5.3 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.020 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
