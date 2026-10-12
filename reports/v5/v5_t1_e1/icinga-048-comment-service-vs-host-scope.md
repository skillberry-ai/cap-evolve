# icinga-048-comment-service-vs-host-scope

<!-- BEGIN:auto -->

**task:** `icinga-048-comment-service-vs-host-scope`  
**category:** icinga  
**origin:** h4-30  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 0.975 |
| h4_t1_e1/e3 | val | 5 | 0.600 |

trial rewards: [1.000, 1.000, 1.000, 1.000, 0.875] · errored trials: 0

delta vs prior arm (h4_t1_e1/e3): 0.375

**cost/time:** $0.4620, 147,728 tokens, 3.9 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id matches one of h4's 30-task held-out set. The prior-arm row above is the mean of two drops of that set, `h4_t1_e1` (Oct-04) and `h4_t1_e3` (Oct-06, harder -- all 5 services declared) -- see [`../../../reports/v4/h4/all-arms-per-trial.md`](../../h4/all-arms-per-trial.md).
