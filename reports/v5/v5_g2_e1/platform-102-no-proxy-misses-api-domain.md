# platform-102-no-proxy-misses-api-domain

<!-- BEGIN:auto -->

**task:** `platform-102-no-proxy-misses-api-domain`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.667 |
| v5_b1_e1 (original skill) | val | 5 | 0.537 |

per-trial rewards: [0.383, 0.650, 0.650, 0.883, 0.767]  
min 0.383 · max 0.883 · spread 0.500 · sd 0.166 · errored trials 0  
delta vs v5_b1_e1: +0.130  

**cost/time:** $0.4214, 118,696 tokens, 32.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.130** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
