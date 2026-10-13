# platform-105-failed-revision-not-main

<!-- BEGIN:auto -->

**task:** `platform-105-failed-revision-not-main`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.598 |

per-trial rewards: [0.710, 0.570, 0.570, 0.570, 0.570]  
min 0.570 · max 0.710 · spread 0.140 · sd 0.056 · errored trials 0  

**cost/time:** $0.3741, 100,733 tokens, 44.4 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.570-0.710 (sd 0.056). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
