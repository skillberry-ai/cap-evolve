# icinga-212-fix-on-main-not-on-pinned-ref

<!-- BEGIN:auto -->

**task:** `icinga-212-fix-on-main-not-on-pinned-ref`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.780 |

per-trial rewards: [0.700, 0.800, 0.900, 0.800, 0.700]  
min 0.700 · max 0.900 · spread 0.200 · sd 0.075 · errored trials 0  

**cost/time:** $1.2576, 372,101 tokens, 13.3 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.700-0.900 (sd 0.075). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
