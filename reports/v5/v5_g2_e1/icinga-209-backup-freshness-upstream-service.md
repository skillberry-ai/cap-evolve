# icinga-209-backup-freshness-upstream-service

<!-- BEGIN:auto -->

**task:** `icinga-209-backup-freshness-upstream-service`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.450 |
| v5_b1_e1 (original skill) | val | 5 | 1.000 |

per-trial rewards: [0.450, 0.333, 0.567, 0.450, 0.450]  
min 0.333 · max 0.567 · spread 0.233 · sd 0.074 · errored trials 0  
delta vs v5_b1_e1: -0.550  

**cost/time:** $2.6759, 833,016 tokens, 29.5 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.550** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
