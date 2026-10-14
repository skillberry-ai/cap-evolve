# cost-053-capacity-dropped-reservations

<!-- BEGIN:auto -->

**task:** `cost-053-capacity-dropped-reservations`  
**category:** cost  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  
**move vs v5_b1_e1:** flat  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 0.872 |
| v5_b1_e1 (original skill) | val | 5 | 0.936 |

per-trial rewards: [1.000, 0.840, 0.680, 1.000, 0.840]  
min 0.680 · max 1.000 · spread 0.320 · sd 0.120 · errored trials 0  
delta vs v5_b1_e1: -0.064  

**cost/time:** $0.8213, 257,749 tokens, 9.1 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

Moved -0.064 vs `v5_b1_e1` -- inside the ~0.09 per-task noise floor; not distinguishable from no change at n=5.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned against this task's v5 content, h4-rewritten or otherwise.
