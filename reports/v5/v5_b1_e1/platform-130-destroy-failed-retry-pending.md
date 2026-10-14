# platform-130-destroy-failed-retry-pending

<!-- BEGIN:auto -->

**task:** `platform-130-destroy-failed-retry-pending`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.748 |

per-trial rewards: [0.440, 1.000, 0.580, 0.860, 0.860]  
min 0.440 · max 1.000 · spread 0.560 · sd 0.206 · errored trials 0  

**cost/time:** $1.6153, 505,238 tokens, 26.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.440-1.000 (sd 0.206). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
