# icinga-013-acknowledged-not-an-issue

<!-- BEGIN:auto -->

**task:** `icinga-013-acknowledged-not-an-issue`  
**category:** icinga  
**task set:** 10-10  
**origin:** v4-34  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.576 |
| v5_b1_e1 (original skill) | val | 5 | 0.480 |

per-trial rewards: [0.640, 0.640, 0.480, 0.640, 0.480]  
min 0.480 · max 0.640 · spread 0.160 · sd 0.078 · errored trials 0  
delta vs v5_b1_e1: +0.096  

**cost/time:** $0.4188, 129,226 tokens, 3.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.096** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** one of v4's original 34 tasks. `cand_0004` was itself optimized against this exact 34-task set in v4's G2 arm, so this is the only group where the skill under test was actually tuned on the task it is being scored on.
