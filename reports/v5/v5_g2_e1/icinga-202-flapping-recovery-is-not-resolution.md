# icinga-202-flapping-recovery-is-not-resolution

<!-- BEGIN:auto -->

**task:** `icinga-202-flapping-recovery-is-not-resolution`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.893 |
| v5_b1_e1 (original skill) | val | 5 | 0.867 |

per-trial rewards: [1.000, 0.867, 0.867, 0.733, 1.000]  
min 0.733 · max 1.000 · spread 0.267 · sd 0.100 · errored trials 0  
delta vs v5_b1_e1: +0.027  

**cost/time:** $0.5733, 174,580 tokens, 18.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.027 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
