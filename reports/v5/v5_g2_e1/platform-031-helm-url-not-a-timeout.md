# platform-031-helm-url-not-a-timeout

<!-- BEGIN:auto -->

**task:** `platform-031-helm-url-not-a-timeout`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.923 |
| v5_b1_e1 (original skill) | val | 5 | 0.660 |

per-trial rewards: [1.000, 0.912, 0.853, 0.940, 0.912]  
min 0.853 · max 1.000 · spread 0.147 · sd 0.048 · errored trials 0  
delta vs v5_b1_e1: +0.264  

**cost/time:** $2.4142, 756,013 tokens, 12.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.264** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
