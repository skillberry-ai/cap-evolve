# platform-122-search-total-not-page

<!-- BEGIN:auto -->

**task:** `platform-122-search-total-not-page`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.776 |
| v5_b1_e1 (original skill) | val | 5 | 0.804 |

per-trial rewards: [0.720, 0.860, 0.720, 0.720, 0.860]  
min 0.720 · max 0.860 · spread 0.140 · sd 0.069 · errored trials 0  
delta vs v5_b1_e1: -0.028  

**cost/time:** $0.3852, 111,688 tokens, 21.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.028 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
