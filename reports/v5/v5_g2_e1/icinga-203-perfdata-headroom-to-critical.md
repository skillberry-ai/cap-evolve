# icinga-203-perfdata-headroom-to-critical

<!-- BEGIN:auto -->

**task:** `icinga-203-perfdata-headroom-to-critical`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.640 |
| v5_b1_e1 (original skill) | val | 5 | 0.672 |

per-trial rewards: [0.640, 0.800, 0.480, 0.640, 0.640]  
min 0.480 · max 0.800 · spread 0.320 · sd 0.101 · errored trials 0  
delta vs v5_b1_e1: -0.032  

**cost/time:** $1.3571, 431,896 tokens, 11.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.032 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
