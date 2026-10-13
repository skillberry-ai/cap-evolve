# platform-040-workshop-cross-cluster-name-search

<!-- BEGIN:auto -->

**task:** `platform-040-workshop-cross-cluster-name-search`  
**category:** platform  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.740 |

per-trial rewards: [0.675, 0.850, 0.675, 0.675, 0.825]  
min 0.675 · max 0.850 · spread 0.175 · sd 0.080 · errored trials 0  

**cost/time:** $0.7559, 239,179 tokens, 13.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.675-0.850 (sd 0.080). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5. h4's numbers for this id describe a different task and are deliberately not shown.
