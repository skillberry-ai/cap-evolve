# cost-050-partial-account-coverage

<!-- BEGIN:auto -->

**task:** `cost-050-partial-account-coverage`  
**category:** cost  
**task set:** 10-10  
**origin:** renamed-content-changed  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.790 |

per-trial rewards: [0.825, 0.825, 0.825, 0.650, 0.825]  
min 0.650 · max 0.825 · spread 0.175 · sd 0.070 · errored trials 0  

**cost/time:** $0.3526, 110,433 tokens, 4.7 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.650-0.825 (sd 0.070). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** kept a v4/h4 task number but has different content, so no earlier number is comparable.
