# cost-051-gcp-net-of-credits

<!-- BEGIN:auto -->

**task:** `cost-051-gcp-net-of-credits`  
**category:** cost  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** yes  
**move vs v5_b1_e1:** up  

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_g2_e1 (cand_0004, reused as-is) | val | 5 | 1.000 |
| v5_b1_e1 (original skill) | val | 5 | 0.840 |

per-trial rewards: [1.000, 1.000, 1.000, 1.000, 1.000]  
min 1.000 · max 1.000 · spread 0.000 · sd 0.000 · errored trials 0  
delta vs v5_b1_e1: +0.160  

**cost/time:** $0.4954, 157,303 tokens, 3.8 min -- see [`../../../results/v5/v5_g2_e1/cost_time/`](../../../results/v5/v5_g2_e1/cost_time/)

<!-- END:auto -->

**Moved up +0.160** vs `v5_b1_e1`, beyond the ~0.09 per-task noise floor.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5 -- `cand_0004` was never tuned against this task's v5 content, h4-rewritten or otherwise.
