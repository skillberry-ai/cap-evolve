# platform-116-timeout-headroom-from-history

<!-- BEGIN:auto -->

**task:** `platform-116-timeout-headroom-from-history`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.728 |
| v5_b1_e1 (original skill) | val | 5 | 0.693 |

per-trial rewards: [0.762, 0.762, 0.762, 0.675, 0.675]  
min 0.675 · max 0.762 · spread 0.087 · sd 0.043 · errored trials 0  
delta vs v5_b1_e1: +0.035  

**cost/time:** $0.5808, 167,148 tokens, 17.6 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.035 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
