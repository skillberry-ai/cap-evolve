# icinga-203-perfdata-headroom-to-critical

<!-- BEGIN:auto -->

**task:** `icinga-203-perfdata-headroom-to-critical`  
**category:** icinga  
**task set:** 10-12  
**origin:** new-10-12  
**deterministic:** no  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.672 |

per-trial rewards: [0.640, 0.800, 0.640, 0.640, 0.640]  
min 0.640 · max 0.800 · spread 0.160 · sd 0.064 · errored trials 0  

**cost/time:** $0.4196, 126,894 tokens, 16.6 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

This task is **non-deterministic**: 5 identical trials spanned 0.640-0.800 (sd 0.064). With n=5 its mean carries a ~95% CI of roughly +/-0.045, so a later arm's change on this task alone is only meaningful well above that. It is one of 76 of 136 v5 tasks (56%) that vary across repeats.

**Lineage:** new in the `v5_2026-10-12` drop -- no earlier measurement.
