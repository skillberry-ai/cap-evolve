# platform-115-find-jobs-default-page-not-the-total

<!-- BEGIN:auto -->

**task:** `platform-115-find-jobs-default-page-not-the-total`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.748 |
| v5_b1_e1 (original skill) | val | 5 | 0.748 |

per-trial rewards: [0.720, 0.720, 0.720, 0.720, 0.860]  
min 0.720 · max 0.860 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: +0.000  

**cost/time:** $1.2987, 418,145 tokens, 9.6 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.000 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** new in the `v5_2026-10-12` drop -- `cand_0004` was never tuned against it.
