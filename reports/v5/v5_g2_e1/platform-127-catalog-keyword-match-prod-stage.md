# platform-127-catalog-keyword-match-prod-stage

<!-- BEGIN:auto -->

**task:** `platform-127-catalog-keyword-match-prod-stage`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.944 |
| v5_b1_e1 (original skill) | val | 5 | 0.832 |

per-trial rewards: [1.000, 1.000, 0.860, 1.000, 0.860]  
min 0.860 · max 1.000 · spread 0.140 · sd 0.069 · errored trials 0  
delta vs v5_b1_e1: +0.112  

**cost/time:** $0.5745, 183,166 tokens, 6.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.112** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
