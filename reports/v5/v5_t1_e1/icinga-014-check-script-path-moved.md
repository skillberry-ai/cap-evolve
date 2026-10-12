# icinga-014-check-script-path-moved

<!-- BEGIN:auto -->

**task:** `icinga-014-check-script-path-moved`  
**category:** icinga  
**origin:** v4-34  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 0.550 |
| v4_t4_e1/e2 | val | 5 | 1.000 |

trial rewards: [0.550, 0.550, 0.550, 0.550, 0.550] · errored trials: 0

delta vs prior arm (v4_t4_e1/e2): -0.450

**cost/time:** $2.2541, 707,369 tokens, 17.3 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id is byte-identical to one of v4's original 34-task set. The prior-arm row above is the mean of two independent zero-shot repeats on that set, `v4_t4_e1`/`v4_t4_e2` -- see [`../../../results/v4/v4_t_e1/cost_time/`](../../../results/v4/v4_t_e1/cost_time/).
