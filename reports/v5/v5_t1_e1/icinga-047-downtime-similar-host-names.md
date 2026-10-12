# icinga-047-downtime-similar-host-names

<!-- BEGIN:auto -->

**task:** `icinga-047-downtime-similar-host-names`  
**category:** icinga  
**origin:** h4-30  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 1.000 |
| h4_t1_e1/e3 | val | 5 | 0.550 |

trial rewards: [1.000, 1.000, 1.000, 1.000, 1.000] · errored trials: 0

delta vs prior arm (h4_t1_e1/e3): 0.450

**cost/time:** $0.4579, 146,484 tokens, 3.5 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id matches one of h4's 30-task held-out set. The prior-arm row above is the mean of two drops of that set, `h4_t1_e1` (Oct-04) and `h4_t1_e3` (Oct-06, harder -- all 5 services declared) -- see [`../../../reports/v4/h4/all-arms-per-trial.md`](../../h4/all-arms-per-trial.md).
