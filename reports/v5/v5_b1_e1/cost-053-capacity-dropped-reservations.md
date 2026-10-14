# cost-053-capacity-dropped-reservations

<!-- BEGIN:auto -->

**task:** `cost-053-capacity-dropped-reservations`  
**category:** cost  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.936 |

per-trial rewards: [1.000, 1.000, 0.680, 1.000, 1.000]  
min 0.680 · max 1.000 · spread 0.320 · sd 0.128 · errored trials 0  

**cost/time:** $0.8597, 266,718 tokens, 8.9 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.680-1.000 (sd 0.128). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5. h4's numbers for this id describe a different task and are deliberately not shown.
