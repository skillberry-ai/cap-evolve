# icinga-202-flapping-recovery-is-not-resolution

<!-- BEGIN:auto -->

**task:** `icinga-202-flapping-recovery-is-not-resolution`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.867 |

per-trial rewards: [0.867, 1.000, 0.733, 0.867, 0.867]  
min 0.733 · max 1.000 · spread 0.267 · sd 0.084 · errored trials 0  

**cost/time:** $0.4092, 119,256 tokens, 16.3 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.733-1.000 (sd 0.084). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
