# platform-040-workshop-cross-cluster-name-search

<!-- BEGIN:auto -->

**task:** `platform-040-workshop-cross-cluster-name-search`  
**category:** platform  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** yes  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.675 |
| v5_b1_e1 (original skill) | val | 5 | 0.740 |

per-trial rewards: [0.675, 0.675, 0.675, 0.675, 0.675]  
min 0.675 · max 0.675 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: -0.065  

**cost/time:** $0.6389, 204,881 tokens, 7.0 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.065 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned against this task's v5 content, h4-rewritten or otherwise.
