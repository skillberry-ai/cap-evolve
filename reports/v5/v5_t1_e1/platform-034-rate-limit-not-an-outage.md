# platform-034-rate-limit-not-an-outage

<!-- BEGIN:auto -->

**task:** `platform-034-rate-limit-not-an-outage`  
**category:** platform  
**origin:** v4-34  
**status:** ok  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| v5_t1_e1 (T1, zero-shot) | val | 5 | 0.785 |
| v4_t4_e1/e2 | val | 5 | 0.992 |

trial rewards: [0.769, 0.692, 0.769, 0.769, 0.925] · errored trials: 0

delta vs prior arm (v4_t4_e1/e2): -0.207

**cost/time:** $0.7857, 222,545 tokens, 30.0 min -- see [`../../../results/v5/v5_t1_e1/cost_time/`](../../../results/v5/v5_t1_e1/cost_time/)

<!-- END:auto -->

This task id is byte-identical to one of v4's original 34-task set. The prior-arm row above is the mean of two independent zero-shot repeats on that set, `v4_t4_e1`/`v4_t4_e2` -- see [`../../../results/v4/v4_t_e1/cost_time/`](../../../results/v4/v4_t_e1/cost_time/).
