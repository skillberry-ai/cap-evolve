# cloud-057-cloudtrail-select-only-refusal

<!-- BEGIN:auto -->

**task:** `cloud-057-cloudtrail-select-only-refusal`  
**category:** cloud  
**task set:** 10-10  
**origin:** h4-rewritten  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.560 |

per-trial rewards: [0.400, 0.400, 0.600, 0.400, 1.000]  
min 0.400 · max 1.000 · spread 0.600 · sd 0.233 · errored trials 0  

**cost/time:** $0.2203, 64,238 tokens, 4.0 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.400-1.000 (sd 0.233). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** shares an id with an h4 held-out task, but its instruction, contract, seed data and verifier were all rewritten going into v5. h4's numbers for this id describe a different task and are deliberately not shown.
