# platform-117-dependency-project-sync-failed

<!-- BEGIN:auto -->

**task:** `platform-117-dependency-project-sync-failed`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.960 |

per-trial rewards: [0.800, 1.000, 1.000, 1.000, 1.000]  
min 0.800 · max 1.000 · spread 0.200 · sd 0.080 · errored trials 0  

**cost/time:** $0.2981, 89,344 tokens, 28.5 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.800-1.000 (sd 0.080). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
