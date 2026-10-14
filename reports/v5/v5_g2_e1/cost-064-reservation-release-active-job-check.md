# cost-064-reservation-release-active-job-check

<!-- BEGIN:auto -->

**task:** `cost-064-reservation-release-active-job-check`  
**category:** cost  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.732 |
| v5_b1_e1 (original skill) | val | 5 | 0.760 |

per-trial rewards: [0.620, 0.760, 0.760, 0.760, 0.760]  
min 0.620 · max 0.760 · spread 0.140 · sd 0.056 · errored trials 0  
delta vs v5_b1_e1: -0.028  

**cost/time:** $1.0730, 332,425 tokens, 10.7 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.028 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned against this task's v5 content, h4-rewritten or otherwise.
