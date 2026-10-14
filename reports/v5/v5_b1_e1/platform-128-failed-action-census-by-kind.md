# platform-128-failed-action-census-by-kind

<!-- BEGIN:auto -->

**task:** `platform-128-failed-action-census-by-kind`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.954 |

per-trial rewards: [0.886, 1.000, 1.000, 0.886, 1.000]  
min 0.886 · max 1.000 · spread 0.114 · sd 0.056 · errored trials 0  

**cost/time:** $0.5994, 174,756 tokens, 5.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.886-1.000 (sd 0.056). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
