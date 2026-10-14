# cost-406-gcp-daily-rows-is-not-day-coverage

<!-- BEGIN:auto -->

**task:** `cost-406-gcp-daily-rows-is-not-day-coverage`  
**category:** cost  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.664 |
| v5_b1_e1 (original skill) | val | 5 | 0.860 |

per-trial rewards: [0.720, 0.720, 0.720, 0.580, 0.580]  
min 0.580 · max 0.720 · spread 0.140 · sd 0.069 · errored trials 0  
delta vs v5_b1_e1: -0.196  

**cost/time:** $1.0061, 308,994 tokens, 13.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.196** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
