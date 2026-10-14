# platform-107-host-pattern-skipped-play

<!-- BEGIN:auto -->

**task:** `platform-107-host-pattern-skipped-play`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.888 |
| v5_b1_e1 (original skill) | val | 5 | 0.858 |

per-trial rewards: [0.860, 0.860, 0.860, 0.860, 1.000]  
min 0.860 · max 1.000 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: +0.030  

**cost/time:** $2.7328, 882,068 tokens, 19.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.030 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
