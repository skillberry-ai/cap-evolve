# icinga-072-alert-output-not-decoy-metrics

<!-- BEGIN:auto -->

**task:** `icinga-072-alert-output-not-decoy-metrics`  
**category:** icinga  
**task set:** 10-10  
**origin:** new-10-10  
**deterministic:** yes  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_b1_e1 (original skill, zero-shot) | val | 5 | 0.000 |

per-trial rewards: [0.000, 0.000, 0.000, 0.000, 0.000]  
min 0.000 · max 0.000 · spread 0.000 · sd 0.000 · errored trials 0  

**cost/time:** $0.6728, 193,175 tokens, 7.2 min -- see [`../../../results/v5/v5_b1_e1/cost_time/`](../../../results/v5/v5_b1_e1/cost_time/)

<!-- END:auto -->

All five trials returned the identical reward, so this task's score carries no run-to-run noise -- unusual here: only 60 of 136 v5 tasks are deterministic.

**Lineage:** new in the `v5_2026-10-10` drop -- no earlier measurement.
