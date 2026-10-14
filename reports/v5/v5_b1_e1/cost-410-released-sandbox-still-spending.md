# cost-410-released-sandbox-still-spending

<!-- BEGIN:auto -->

**task:** `cost-410-released-sandbox-still-spending`  
**category:** cost  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.544 |

per-trial rewards: [0.340, 0.620, 0.520, 0.480, 0.760]  
min 0.340 · max 0.760 · spread 0.420 · sd 0.141 · errored trials 0  

**cost/time:** $0.8743, 256,399 tokens, 20.7 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.340-0.760 (sd 0.141). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
