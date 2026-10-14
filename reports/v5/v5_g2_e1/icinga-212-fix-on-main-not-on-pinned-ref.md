# icinga-212-fix-on-main-not-on-pinned-ref

<!-- BEGIN:auto -->

**task:** `icinga-212-fix-on-main-not-on-pinned-ref`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.820 |
| v5_b1_e1 (original skill) | val | 5 | 0.780 |

per-trial rewards: [0.800, 0.900, 0.800, 0.800, 0.800]  
min 0.800 · max 0.900 · spread 0.100 · sd 0.040 · errored trials 0  
delta vs v5_b1_e1: +0.040  

**cost/time:** $2.5990, 817,463 tokens, 27.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.040 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
