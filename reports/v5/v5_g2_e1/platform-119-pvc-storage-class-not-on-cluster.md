# platform-119-pvc-storage-class-not-on-cluster

<!-- BEGIN:auto -->

**task:** `platform-119-pvc-storage-class-not-on-cluster`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.972 |
| v5_b1_e1 (original skill) | val | 5 | 0.944 |

per-trial rewards: [1.000, 0.860, 1.000, 1.000, 1.000]  
min 0.860 · max 1.000 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: +0.028  

**cost/time:** $0.5284, 153,776 tokens, 6.3 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.028 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
