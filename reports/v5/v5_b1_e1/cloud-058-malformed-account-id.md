# cloud-058-malformed-account-id

<!-- BEGIN:auto -->

**task:** `cloud-058-malformed-account-id`  
**category:** cloud  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.600 |

per-trial rewards: [0.600, 0.600, 0.600, 0.600, 0.600]  
min 0.600 · max 0.600 · spread 0.000 · sd 0.000 · errored trials 0  

**cost/time:** $0.1598, 51,397 tokens, 2.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 60 of 136 v5 tasks are deterministic.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5. h4's numbers for this id describe a different task and are deliberately not shown.
