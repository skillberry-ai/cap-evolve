# cloud-057-cloudtrail-select-only-refusal

<!-- BEGIN:auto -->

**task:** `cloud-057-cloudtrail-select-only-refusal`  
**category:** cloud  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.640 |
| v5_b1_e1 (original skill) | val | 5 | 0.560 |

per-trial rewards: [0.400, 0.400, 0.400, 1.000, 1.000]  
min 0.400 · max 1.000 · spread 0.600 · sd 0.294 · errored trials 0  
delta vs v5_b1_e1: +0.080  

**cost/time:** $0.3515, 106,782 tokens, 3.2 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved +0.080 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned against this task's v5 content, h4-rewritten or otherwise.
