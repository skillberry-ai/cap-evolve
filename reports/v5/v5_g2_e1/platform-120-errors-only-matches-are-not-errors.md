# platform-120-errors-only-matches-are-not-errors

<!-- BEGIN:auto -->

**task:** `platform-120-errors-only-matches-are-not-errors`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.808 |
| v5_b1_e1 (original skill) | val | 5 | 0.712 |

per-trial rewards: [1.000, 0.520, 1.000, 0.840, 0.680]  
min 0.520 · max 1.000 · spread 0.480 · sd 0.187 · errored trials 0  
delta vs v5_b1_e1: +0.096  

**cost/time:** $0.3024, 89,206 tokens, 8.5 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.096** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
