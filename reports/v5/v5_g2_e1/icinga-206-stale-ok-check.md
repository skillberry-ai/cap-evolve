# icinga-206-stale-ok-check

<!-- BEGIN:auto -->

**task:** `icinga-206-stale-ok-check`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.680 |
| v5_b1_e1 (original skill) | val | 5 | 0.653 |

per-trial rewards: [0.733, 0.600, 0.600, 0.733, 0.733]  
min 0.600 · max 0.733 · spread 0.133 · sd 0.065 · errored trials 0  
delta vs v5_b1_e1: +0.027  

**cost/time:** $0.5516, 171,512 tokens, 6.9 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.027 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
