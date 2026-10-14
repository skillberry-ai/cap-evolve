# platform-001-ee-entrypoint-rca

<!-- BEGIN:auto -->

**task:** `platform-001-ee-entrypoint-rca`  
**category:** platform  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.748 |
| v5_b1_e1 (original skill) | val | 5 | 0.480 |

per-trial rewards: [0.660, 0.760, 1.000, 0.660, 0.660]  
min 0.660 · max 1.000 · spread 0.340 · sd 0.132 · errored trials 0  
delta vs v5_b1_e1: +0.268  

**cost/time:** $0.3815, 107,410 tokens, 19.5 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.268** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
