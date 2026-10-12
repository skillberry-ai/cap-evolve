# platform-001-ee-entrypoint-rca

<!-- BEGIN:auto -->

**task:** `platform-001-ee-entrypoint-rca`  
**category:** platform  
**origin:** v4-34  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 0.884 |
| v4_t4_e1/e2 | val | 5 | 0.728 |

trial rewards: [0.760, 0.900, 1.000, 0.760, 1.000] · errored trials: 0

delta vs prior arm (v4_t4_e1/e2): 0.156

**cost/time:** $0.3866, 108,894 tokens, 17.2 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id is byte-identical to one of v4's original 34-task set. The prior-arm row above is the mean of two independent zero-shot repeats on that set, `v4_t4_e1`/`v4_t4_e2` -- see [`../../../results/v4/v4_t_e1/cost_time/`](../../../results/v4/v4_t_e1/cost_time/).
