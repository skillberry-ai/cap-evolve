# icinga-213-host-down-is-paused-vm

<!-- BEGIN:auto -->

**task:** `icinga-213-host-down-is-paused-vm`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** yes  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.450 |
| v5_b1_e1 (original skill) | val | 5 | 0.450 |

per-trial rewards: [0.450, 0.450, 0.450, 0.450, 0.450]  
min 0.450 · max 0.450 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: +0.000  

**cost/time:** $3.6083, 1,133,178 tokens, 40.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.000 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
