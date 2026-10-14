# platform-105-failed-revision-not-main

<!-- BEGIN:auto -->

**task:** `platform-105-failed-revision-not-main`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.654 |
| v5_b1_e1 (original skill) | val | 5 | 0.598 |

per-trial rewards: [0.570, 0.570, 0.570, 0.710, 0.850]  
min 0.570 · max 0.850 · spread 0.280 · sd 0.112 · errored trials 0  
delta vs v5_b1_e1: +0.056  

**cost/time:** $0.4261, 117,707 tokens, 31.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.056 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
