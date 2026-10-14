# icinga-211-thresholds-file-never-deployed

<!-- BEGIN:auto -->

**task:** `icinga-211-thresholds-file-never-deployed`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.200 |
| v5_b1_e1 (original skill) | val | 5 | 0.180 |

per-trial rewards: [0.100, 0.300, 0.200, 0.200, 0.200]  
min 0.100 · max 0.300 · spread 0.200 · sd 0.063 · errored trials 0  
delta vs v5_b1_e1: +0.020  

**cost/time:** $0.4143, 126,726 tokens, 3.4 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.020 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
