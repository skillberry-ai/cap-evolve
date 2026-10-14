# icinga-210-command-vars-override-script-default

<!-- BEGIN:auto -->

**task:** `icinga-210-command-vars-override-script-default`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.957 |
| v5_b1_e1 (original skill) | val | 5 | 1.000 |

per-trial rewards: [0.883, 0.900, 1.000, 1.000, 1.000]  
min 0.883 · max 1.000 · spread 0.117 · sd 0.053 · errored trials 0  
delta vs v5_b1_e1: -0.043  

**cost/time:** $1.0087, 307,969 tokens, 14.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.043 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
