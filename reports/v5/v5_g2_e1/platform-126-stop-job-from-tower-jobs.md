# platform-126-stop-job-from-tower-jobs

<!-- BEGIN:auto -->

**task:** `platform-126-stop-job-from-tower-jobs`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.940 |
| v5_b1_e1 (original skill) | val | 5 | 0.850 |

per-trial rewards: [0.850, 0.850, 1.000, 1.000, 1.000]  
min 0.850 · max 1.000 · spread 0.150 · sd 0.073 · errored trials 0  
delta vs v5_b1_e1: +0.090  

**cost/time:** $0.8651, 277,220 tokens, 11.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.090** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
