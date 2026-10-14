# platform-113-account-region-override-not-capacity

<!-- BEGIN:auto -->

**task:** `platform-113-account-region-override-not-capacity`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.795 |
| v5_b1_e1 (original skill) | val | 4 | 0.744 |

per-trial rewards: [0.825, 0.662, 0.838, 0.912, 0.738]  
min 0.662 · max 0.912 · spread 0.250 · sd 0.086 · errored trials 0  
delta vs v5_b1_e1: +0.051  

**cost/time:** $0.5922, 168,674 tokens, 28.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.051 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
