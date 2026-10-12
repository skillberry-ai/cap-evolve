# platform-008-log-does-not-say

<!-- BEGIN:auto -->

**task:** `platform-008-log-does-not-say`  
**category:** platform  
**origin:** v4-34  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 0.920 |
| v4_t4_e1/e2 | val | 5 | 1.000 |

trial rewards: [0.800, 1.000, 0.800, 1.000, 1.000] · errored trials: 0

delta vs prior arm (v4_t4_e1/e2): -0.080

**cost/time:** $0.3263, 99,149 tokens, 13.1 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id is byte-identical to one of v4's original 34-task set. The prior-arm row above is the mean of two independent zero-shot repeats on that set, `v4_t4_e1`/`v4_t4_e2` -- see [`../../../results/v4/v4_t_e1/cost_time/`](../../../results/v4/v4_t_e1/cost_time/).
