# platform-135-catalog-component-drift-fanout

<!-- BEGIN:auto -->

**task:** `platform-135-catalog-component-drift-fanout`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** down  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.774 |
| v5_b1_e1 (original skill) | val | 5 | 0.916 |

per-trial rewards: [0.860, 0.860, 0.860, 0.430, 0.860]  
min 0.430 · max 0.860 · spread 0.430 · sd 0.172 · errored trials 0  
delta vs v5_b1_e1: -0.142  

**cost/time:** $2.0127, 642,324 tokens, 27.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved down -0.142** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
