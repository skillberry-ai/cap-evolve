# platform-068-deprecation-warning-not-the-fatal

<!-- BEGIN:auto -->

**task:** `platform-068-deprecation-warning-not-the-fatal`  
**category:** platform  
**task set:** 10-10  
**origin:** new-10-10  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.860 |
| v5_b1_e1 (original skill) | val | 5 | 0.944 |

per-trial rewards: [0.860, 1.000, 1.000, 1.000, 0.440]  
min 0.440 · max 1.000 · spread 0.560 · sd 0.217 · errored trials 0  
delta vs v5_b1_e1: -0.084  

**cost/time:** $1.7892, 572,820 tokens, 10.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.084 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-10` drop -- `cand_0004` was never tuned against it.
