# platform-128-failed-action-census-by-kind

<!-- BEGIN:auto -->

**task:** `platform-128-failed-action-census-by-kind`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** yes  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.886 |
| v5_b1_e1 (original skill) | val | 5 | 0.954 |

per-trial rewards: [0.886, 0.886, 0.886, 0.886, 0.886]  
min 0.886 · max 0.886 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: -0.069  

**cost/time:** $0.6450, 193,867 tokens, 6.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.069 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
