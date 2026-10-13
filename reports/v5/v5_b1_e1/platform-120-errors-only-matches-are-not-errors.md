# platform-120-errors-only-matches-are-not-errors

<!-- BEGIN:auto -->

**task:** `platform-120-errors-only-matches-are-not-errors`  
**category:** platform  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.712 |

per-trial rewards: [0.680, 0.680, 0.840, 0.680, 0.680]  
min 0.680 · max 0.840 · spread 0.160 · sd 0.064 · errored trials 0  

**cost/time:** $0.2470, 70,521 tokens, 4.7 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.680-0.840 (sd 0.064). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
