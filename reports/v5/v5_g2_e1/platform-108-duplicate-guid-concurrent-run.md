# platform-108-duplicate-guid-concurrent-run

<!-- BEGIN:auto -->

**task:** `platform-108-duplicate-guid-concurrent-run`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.807 |
| v5_b1_e1 (original skill) | val | 5 | 0.783 |

per-trial rewards: [0.783, 0.783, 0.900, 0.667, 0.900]  
min 0.667 · max 0.900 · spread 0.233 · sd 0.087 · errored trials 0  
delta vs v5_b1_e1: +0.023  

**cost/time:** $0.5835, 167,406 tokens, 38.6 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.023 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
